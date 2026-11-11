"""Auto arrange picker: previews of each arrangement style on your own screen.

Each card is a small picture of the monitor and your widgets as they would
sit in that style. Clicking a card arranges the real
desktop right away so you can see it; Keep this keeps it, Cancel puts every
widget back where it was.
"""
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from desktop_widgets import config
from desktop_widgets import theme as th
from desktop_widgets.theme import CHROMA, TYPE, mix
from desktop_widgets.services import arrange
from desktop_widgets.services.screens import area_for
from desktop_widgets.ui.components import paint_shell, RoundedButton
from desktop_widgets.ui.drawing import rounded_rect

THUMB_W = 224
CARD_GAP = 12
SIDE = 28


class ArrangeScreen:
    def __init__(self, mgr):
        self.mgr = mgr
        self.t = t = config.get_theme(mgr.data)
        self.chosen = None              # style currently tried on the desktop
        self.started = False            # whether the desktop has been changed yet
        self._photos = {}

        inputs = mgr._arrange_inputs()
        self.blocks, by_area = inputs
        # Preview the monitor that holds the most widgets.
        self.area = max(by_area, key=lambda a: len(by_area[a])) if by_area else \
            area_for(mgr.root, 0, 0)
        self.widgets = by_area.get(self.area, [])
        al, at, ar, ab = self.area
        self.thumb_h = round(THUMB_W * (ab - at) / max(1, ar - al))
        self.scale = THUMB_W / max(1, ar - al)
        current = {w: {"x": w._win_x(), "y": w._win_y(), "rw": w.W, "rh": w.H} for w in self.widgets}
        self.plans = [("current", "As it is now", "Your current arrangement", current)]
        for key, name, hint in arrange.STYLES:
            spots = mgr.plan_arrangement(key, inputs)
            self.plans.append((key, name, hint, {w: s for w, s in spots.items() if w in self.widgets}))

        cols = 3
        rows = -(-len(self.plans) // cols)
        card_h = self.thumb_h + 52
        self.W = W = 2 * SIDE + cols * THUMB_W + (cols - 1) * CARD_GAP
        self.H = H = 92 + rows * card_h + (rows - 1) * CARD_GAP + 84
        left, top, right, bottom = area_for(mgr.root, mgr.root.winfo_pointerx(), mgr.root.winfo_pointery())
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", CHROMA)
        self.win.configure(bg=CHROMA)
        self.win.geometry(f"{W}x{H}+{left + (right - left - W) // 2}+{top + (bottom - top - H) // 2}")
        self.win.bind("<Escape>", lambda e: self.cancel())
        self.cv = cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        paint_shell(cv, W, H, t, "Arrange your desktop", self.cancel,
                    "Click a style to try it on your desktop")
        self._drag(cv)

        self.cards = {}
        for i, (key, name, hint, spots) in enumerate(self.plans):
            x = SIDE + (i % cols) * (THUMB_W + CARD_GAP)
            y = 88 + (i // cols) * (card_h + CARD_GAP)
            self.cards[key] = (x, y, card_h)
            photo = ImageTk.PhotoImage(self._preview(spots), master=cv)
            self._photos[key] = photo
            tag = f"card_{key}"
            cv.create_image(x, y, image=photo, anchor="nw", tags=tag)
            cv.create_text(x + 2, y + self.thumb_h + 18, text=name, anchor="w", fill=t.txt,
                           font=TYPE["strong"], tags=tag)
            cv.create_text(x + 2, y + self.thumb_h + 37, text=hint, anchor="w", fill=t.txt2,
                           font=TYPE["caption"], tags=tag)
            cv.tag_bind(tag, "<ButtonRelease-1>", lambda e, k=key: self.choose(k))
            cv.tag_bind(tag, "<Enter>", lambda e: cv.config(cursor="hand2"))
            cv.tag_bind(tag, "<Leave>", lambda e: cv.config(cursor=""))
        self._draw_rings()

        cv.create_line(1, H - 72, W - 1, H - 72, fill=t.border)
        self.status = tk.Label(cv, text="Nothing has changed yet.", bg=t.bg, fg=t.txt2,
                               font=TYPE["caption"])
        self.status.place(x=SIDE, y=H - 36, anchor="w")
        RoundedButton(cv, "Cancel", self.cancel, t, width=96, height=32).place(
            x=W - SIDE - 96 - 8 - 120, y=H - 52)
        self.keep_button = None
        self._footer()
        self.win.focus_force()

    # ── Previews ───────────────────────────────────────────

    def _app_colors(self, widget):
        from desktop_widgets.ui.tiles import icon_color
        blk = self.blocks.get(widget, {})
        apps = blk.get("apps") or blk.get("files") or []
        if hasattr(widget, "group"):
            apps = widget.group.get("apps", apps)
        colors = []
        for app in apps[:60]:
            try:
                colors.append(icon_color(app, self.t.txt2))
            except Exception:
                colors.append(self.t.txt2)
        return colors

    def _preview(self, spots):
        """The monitor in miniature with every widget as it would sit."""
        S, t = 2, self.t
        k = self.scale * S
        al, at = self.area[0], self.area[1]
        # A plain screen in the theme's colours: a little darker than the widgets.
        screen = mix(t.bg, "#000000" if not th.is_light(t) else "#ffffff", 0.45)
        img = Image.new("RGBA", (THUMB_W * S, self.thumb_h * S), screen)
        d = ImageDraw.Draw(img)
        for widget, spot in spots.items():
            x1, y1 = (spot["x"] - al) * k, (spot["y"] - at) * k
            x2, y2 = x1 + spot["rw"] * k, y1 + spot["rh"] * k
            d.rounded_rectangle((x1, y1, x2, y2), radius=max(2, 6 * k), fill=t.bg,
                                outline=mix(t.bg, t.txt, 0.18))
            hdr = 40 * k
            d.rounded_rectangle((x1 + 4 * k * 3, y1 + hdr * 0.38, x1 + min(x2 - x1, 150 * k), y1 + hdr * 0.58),
                                radius=2, fill=mix(t.bg, t.txt, 0.45))
            kind = getattr(widget, "__class__").__name__
            body_top = y1 + hdr + (36 * k if kind == "StackWidget" else 0)
            if kind in ("GroupWidget", "StackWidget", "DocsWidget") and not widget._collapsed:
                cols = max(1, round((spot["rw"] - 28) / 88))
                cell_w, cell_h = (spot["rw"] - 28) / cols * k, 90 * k
                size = min(cell_w, cell_h) * 0.5
                for i, color in enumerate(self._app_colors(widget)):
                    cx = x1 + 14 * k + (i % cols + 0.5) * cell_w
                    cy = body_top + (i // cols + 0.42) * cell_h
                    if cy + size / 2 > y2 - 4:
                        break
                    d.rounded_rectangle((cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2),
                                        radius=max(1, size * 0.25), fill=color)
            elif kind == "StatsPlusWidget":
                pts = [(x1 + 20 * k + i * (x2 - x1 - 40 * k) / 9,
                        y1 + hdr + 100 * k - [30, 45, 38, 60, 52, 70, 58, 80, 66, 74][i] * k) for i in range(10)]
                d.line(pts, fill=t.accent, width=max(1, round(2 * k)))
            elif kind == "MediaWidget":
                a = 120 * k
                d.rounded_rectangle((x1 + 30 * k, y1 + hdr + 16 * k, x1 + 30 * k + a, y1 + hdr + 16 * k + a),
                                    radius=3, fill=mix(t.accent, t.bg, 0.35))
                d.ellipse((x1 + (x2 - x1) / 2 - 22 * k, y2 - 70 * k, x1 + (x2 - x1) / 2 + 22 * k, y2 - 26 * k),
                          fill=t.accent)
            elif kind == "NotesWidget":
                for i in range(4):
                    yy = y1 + hdr + (24 + i * 26) * k
                    if yy > y2 - 10:
                        break
                    d.line((x1 + 20 * k, yy, x2 - (40 + 50 * (i % 2)) * k, yy),
                           fill=mix(t.bg, t.txt, 0.35), width=max(1, round(3 * k)))
        img = img.resize((THUMB_W, self.thumb_h), Image.Resampling.LANCZOS)
        mask = Image.new("L", img.size)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, THUMB_W - 1, self.thumb_h - 1), radius=6, fill=255)
        out = Image.new("RGBA", img.size, t.bg)
        out.paste(img, (0, 0), mask)
        return out

    def _draw_rings(self):
        self.cv.delete("ring")
        selected = self.chosen or "current"
        for key, (x, y, card_h) in self.cards.items():
            on = key == selected
            item = rounded_rect(self.cv, x - 3, y - 3, x + THUMB_W + 3, y + self.thumb_h + 3, 8,
                                outline=self.t.accent if on else self.t.border, width=2 if on else 1)
            self.cv.addtag_withtag("ring", item)
            self.cv.tag_lower(item)

    # ── Choosing ───────────────────────────────────────────

    def choose(self, key):
        if key == (self.chosen or "current"):
            return
        if key == "current":
            snap = self.mgr.data.get("arrange_undo")
            if self.started and snap:
                self.mgr._apply_snapshot(snap, animate=True)
            self.chosen = None
        else:
            self.mgr.auto_arrange(key, keep_undo=self.started)
            self.started = True
            self.chosen = key
        self._draw_rings()
        self._footer()
        self.win.lift()

    def _footer(self):
        if self.keep_button:
            self.keep_button.destroy()
        trying = self.chosen is not None
        self.keep_button = RoundedButton(self.cv, "Keep this" if trying else "Done",
                                         self.keep, self.t, accent=trying, width=120, height=32)
        self.keep_button.place(x=self.W - SIDE - 120, y=self.H - 52)
        if trying:
            name = next(n for k, n, *_ in self.plans if k == self.chosen)
            self.status.configure(text=f"Trying “{name}”. Keep it, or pick another.")
        elif self.started:
            self.status.configure(text="Back to your own arrangement.")

    def keep(self):
        if self.chosen is None and self.started:
            self.mgr.data.pop("arrange_undo", None)        # back where it started: nothing to undo
            config.save(self.mgr.data)
        self.win.destroy()

    def cancel(self):
        if self.started and self.chosen is not None:
            self.mgr.undo_auto_arrange()
        elif self.started:
            self.mgr.data.pop("arrange_undo", None)
            config.save(self.mgr.data)
        self.win.destroy()

    def _drag(self, cv):
        def press(e):
            self._drag_from = ((e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())
                               if e.y < 76 and e.x < self.W - 60 else None)
        def move(e):
            if getattr(self, "_drag_from", None):
                dx, dy = self._drag_from
                self.win.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")
        cv.bind("<ButtonPress-1>", press, add="+")
        cv.bind("<B1-Motion>", move, add="+")
