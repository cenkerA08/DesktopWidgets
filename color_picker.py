"""
color_picker.py — Custom circular HSV color picker.
Shows a hue wheel ring, a SV triangle/square in the center,
and a hex input field. No external dependencies beyond PIL.
"""
from __future__ import annotations
import tkinter as tk
import math
from typing import Callable

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int,int,int]:
    """h 0-360, s 0-1, v 0-1 → r,g,b 0-255"""
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if   h < 60:  r,g,b = c,x,0
    elif h < 120: r,g,b = x,c,0
    elif h < 180: r,g,b = 0,c,x
    elif h < 240: r,g,b = 0,x,c
    elif h < 300: r,g,b = x,0,c
    else:         r,g,b = c,0,x
    return int((r+m)*255), int((g+m)*255), int((b+m)*255)


def _rgb_to_hsv(r: int, g: int, b: int) -> tuple[float,float,float]:
    r,g,b = r/255, g/255, b/255
    mx, mn = max(r,g,b), min(r,g,b)
    v = mx; d = mx - mn
    s = 0 if mx == 0 else d / mx
    if d == 0: h = 0
    elif mx == r: h = 60 * (((g-b)/d) % 6)
    elif mx == g: h = 60 * ((b-r)/d + 2)
    else:         h = 60 * ((r-g)/d + 4)
    return h, s, v


def _hex_to_rgb(hex_str: str) -> tuple[int,int,int]:
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c*2 for c in hex_str)
    return int(hex_str[0:2],16), int(hex_str[2:4],16), int(hex_str[4:6],16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _make_wheel(size: int, ring_w: int) -> "Image.Image":
    """Render the hue ring."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size // 2
    r_out = cx - 2
    r_in  = r_out - ring_w
    for y in range(size):
        for x in range(size):
            dx = x - cx; dy = y - cy
            dist = math.sqrt(dx*dx + dy*dy)
            if r_in <= dist <= r_out:
                angle = math.degrees(math.atan2(dy, dx)) % 360
                rgb = _hsv_to_rgb(angle, 1.0, 1.0)
                img.putpixel((x, y), (*rgb, 255))
    return img


def _make_sv_square(size: int, hue: float) -> "Image.Image":
    """Render a saturation-value square for a given hue."""
    img = Image.new("RGB", (size, size))
    for y in range(size):
        v = 1.0 - y / size
        for x in range(size):
            s = x / size
            rgb = _hsv_to_rgb(hue, s, v)
            img.putpixel((x, y), rgb)
    return img


class ColorPicker(tk.Toplevel):
    """
    Standalone color picker window.
    callback(hex_color) is called whenever the color changes.
    """
    WHEEL_SIZE = 220
    RING_W     = 24
    SV_SIZE    = 110

    def __init__(self, parent: tk.Misc, initial: str = "#5b7cf8",
                 callback: Callable[[str], None] | None = None,
                 title: str = "Pick a color"):
        super().__init__(parent)
        self.title("")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self._callback = callback
        self._updating = False

        # Parse initial color
        try:
            r, g, b = _hex_to_rgb(initial)
        except Exception:
            r, g, b = 91, 124, 248
        self._h, self._s, self._v = _rgb_to_hsv(r, g, b)

        # Styling
        BG = "#1c1f26"; HDR = "#14161c"; BORDER = "#3a3e4a"
        TXT = "#f0f0f0"; TXT2 = "#9098aa"; ACCENT = "#5b7cf8"
        self._bg = BG

        self.configure(bg=BG)

        # ── Header ──
        hdr = tk.Frame(self, bg=HDR, height=36)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=title, font=("Segoe UI", 9, "bold"),
                 bg=HDR, fg=TXT).pack(side="left", padx=12, pady=8)
        tk.Button(hdr, text="✕", font=("Segoe UI", 10), bg=HDR, fg=TXT2,
                  activebackground=HDR, activeforeground="#ff5555",
                  relief="flat", bd=0, cursor="hand2",
                  command=self.destroy).pack(side="right", padx=8)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── Color wheel canvas ──
        self._cv = tk.Canvas(self, bg=BG, highlightthickness=0,
                             width=self.WHEEL_SIZE, height=self.WHEEL_SIZE)
        self._cv.pack(padx=16, pady=12)

        # ── Hex input + preview ──
        bot = tk.Frame(self, bg=BG)
        bot.pack(fill="x", padx=16, pady=(0, 12))

        self._preview = tk.Frame(bot, width=36, height=28,
                                  highlightbackground=BORDER,
                                  highlightthickness=1)
        self._preview.pack(side="left", padx=(0, 8))

        self._hex_var = tk.StringVar(value=_rgb_to_hex(r, g, b))
        self._hex_entry = tk.Entry(bot, textvariable=self._hex_var,
                                    font=("Consolas", 11),
                                    bg="#0e1118", fg=TXT,
                                    insertbackground=TXT,
                                    relief="flat", bd=0,
                                    highlightthickness=1,
                                    highlightcolor=ACCENT,
                                    highlightbackground=BORDER,
                                    width=9)
        self._hex_entry.pack(side="left", ipady=4)
        self._hex_var.trace_add("write", self._on_hex_change)

        # OK button
        tk.Button(bot, text="OK", font=("Segoe UI", 9, "bold"),
                  bg=ACCENT, fg="white", activebackground="#4a6be8",
                  relief="flat", bd=0, padx=14, pady=4, cursor="hand2",
                  command=self._confirm).pack(side="right")

        # Render wheel
        if PIL_OK:
            self._wheel_img_raw = _make_wheel(self.WHEEL_SIZE, self.RING_W)
            self._wheel_photo   = ImageTk.PhotoImage(self._wheel_img_raw)
            self._cv.create_image(0, 0, anchor="nw", image=self._wheel_photo,
                                   tags="wheel")

        self._draw_sv()
        self._draw_markers()
        self._update_preview()

        # Bind mouse
        self._cv.bind("<ButtonPress-1>",   self._on_press)
        self._cv.bind("<B1-Motion>",       self._on_drag)
        self._cv.bind("<ButtonRelease-1>", self._on_release)

        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width()  // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w  = self.winfo_width(); h = self.winfo_height()
        self.geometry(f"+{pw - w//2}+{ph - h//2}")

    # ── Drawing ────────────────────────────────────────────

    def _draw_sv(self):
        """Draw the SV square in the center."""
        if not PIL_OK: return
        sz  = self.SV_SIZE
        img = _make_sv_square(sz, self._h)
        self._sv_photo = ImageTk.PhotoImage(img)
        cx = cy = self.WHEEL_SIZE // 2
        x0 = cx - sz//2; y0 = cy - sz//2
        self._sv_x0, self._sv_y0 = x0, y0
        self._cv.delete("sv")
        self._cv.create_image(x0, y0, anchor="nw", image=self._sv_photo,
                               tags="sv")

    def _draw_markers(self):
        """Draw hue ring marker and SV crosshair."""
        self._cv.delete("marker")
        cx = cy = self.WHEEL_SIZE // 2
        r_mid = cx - 2 - self.RING_W // 2

        # Hue marker on ring
        a = math.radians(self._h)
        mx = cx + r_mid * math.cos(a)
        my = cy + r_mid * math.sin(a)
        self._cv.create_oval(mx-7, my-7, mx+7, my+7,
                              outline="white", width=2, tags="marker")
        self._cv.create_oval(mx-5, my-5, mx+5, my+5,
                              outline="black", width=1, tags="marker")

        # SV crosshair
        sz = self.SV_SIZE
        sx = self._sv_x0 + int(self._s * sz)
        sy = self._sv_y0 + int((1 - self._v) * sz)
        self._cv.create_oval(sx-6, sy-6, sx+6, sy+6,
                              outline="white", width=2, tags="marker")
        self._cv.create_oval(sx-4, sy-4, sx+4, sy+4,
                              outline="black", width=1, tags="marker")

    def _update_preview(self):
        r, g, b = _hsv_to_rgb(self._h, self._s, self._v)
        hex_col = _rgb_to_hex(r, g, b)
        self._preview.config(bg=hex_col)
        self._updating = True
        self._hex_var.set(hex_col)
        self._updating = False
        if self._callback:
            self._callback(hex_col)

    # ── Mouse ──────────────────────────────────────────────

    def _on_press(self, e): self._handle(e.x, e.y)
    def _on_drag(self, e):  self._handle(e.x, e.y)
    def _on_release(self, e): pass

    def _handle(self, x: int, y: int):
        cx = cy = self.WHEEL_SIZE // 2
        dx = x - cx; dy = y - cy
        dist = math.sqrt(dx*dx + dy*dy)
        r_out = cx - 2; r_in = r_out - self.RING_W

        if dist >= r_in:
            # On the hue ring (or outside — clamp to ring)
            self._h = math.degrees(math.atan2(dy, dx)) % 360
            self._draw_sv()
            self._draw_markers()
            self._update_preview()
        else:
            # Inside SV square
            sz = self.SV_SIZE
            sx = x - self._sv_x0; sy = y - self._sv_y0
            self._s = max(0.0, min(1.0, sx / sz))
            self._v = max(0.0, min(1.0, 1.0 - sy / sz))
            self._draw_markers()
            self._update_preview()

    def _on_hex_change(self, *_):
        if self._updating: return
        val = self._hex_var.get().strip()
        if not val.startswith("#"): val = "#" + val
        try:
            r, g, b = _hex_to_rgb(val)
            self._h, self._s, self._v = _rgb_to_hsv(r, g, b)
            self._draw_sv()
            self._draw_markers()
            self._preview.config(bg=_rgb_to_hex(r, g, b))
            if self._callback: self._callback(_rgb_to_hex(r, g, b))
        except Exception:
            pass

    def _confirm(self):
        r, g, b = _hsv_to_rgb(self._h, self._s, self._v)
        if self._callback:
            self._callback(_rgb_to_hex(r, g, b))
        self.destroy()


def ask_color(parent: tk.Misc, initial: str = "#5b7cf8",
              title: str = "Pick a color",
              callback: Callable[[str], None] | None = None) -> ColorPicker:
    """Open a color picker. Returns the picker window (non-blocking)."""
    picker = ColorPicker(parent, initial=initial, callback=callback, title=title)
    return picker