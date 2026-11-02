"""
statsplus_widget.py — Stats+ widget.
Each tile is rendered offscreen with PIL at 2x then downscaled — crisp arcs, no pixelation.
Width fixed by column count. Only collapses, no resize.
"""
from __future__ import annotations
import subprocess, threading, time, math
from collections import deque
from typing import TYPE_CHECKING

import tkinter as tk
from desktop_widgets.theme import HDR_H, INSET, R_TILE, R_PANEL
from desktop_widgets.widgets.base_widget import BaseWidget
import desktop_widgets.config as config

if TYPE_CHECKING:
    from desktop_widgets.manager import Manager

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageFilter
    PIL_OK = True
except ImportError:
    PIL_OK = False


ALL_METRICS = [
    ("cpu_pct",   "CPU",       "%",    100),
    ("cpu_temp",  "CPU Temp",  "°C",   110),
    ("ram_pct",   "RAM",       "%",    100),
    ("ram_used",  "RAM Used",  "GB",   None),
    ("gpu_pct",   "GPU",       "%",    100),
    ("gpu_temp",  "GPU Temp",  "°C",   110),
    ("disk_r",    "Disk R",    "MB/s", None),
    ("disk_w",    "Disk W",    "MB/s", None),
    ("net_up",    "Net Up",    "MB/s", None),
    ("net_down",  "Net Down",  "MB/s", None),
    ("uptime",    "Uptime",    "",     None),
]
DEFAULT_METRICS = ["cpu_pct", "cpu_temp", "ram_pct", "gpu_pct", "gpu_temp"]

TILE_H   = 124
GAP      = 8       # space between tiles
MIN_COLS = 1
MAX_COLS = 4
DEF_COLS = 2
SCALE    = 3      # render at 3x, downscale for antialiasing


def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


def _lerp_color(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    ar, ag, ab = _hex(a); br, bg, bb = _hex(b)
    return "#{:02x}{:02x}{:02x}".format(
        int(ar+(br-ar)*t), int(ag+(bg-ag)*t), int(ab+(bb-ab)*t))


def _metric_color(pct: float, t) -> str:
    """Clear load colours: theme colour while relaxed, then warning, then danger.
    (Blending between them produced muddy browns in the middle range.)"""
    if pct < 0.6:
        return t.ok
    if pct < 0.85:
        return t.warn
    return t.danger


def _hex_rgba(c: str, a: int = 255) -> tuple:
    r, g, b = _hex(c)
    return (r, g, b, a)


def _font(name: str, size: int):
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


HERO_H = 136      # top card with the big number and live graph
CARD_H = 78       # smaller cards for the remaining metrics
HISTORY = 60      # samples kept per metric (~90 s at 1.5 s per poll)


def _area_chart(img, d, box, values, color, base_bg, S, line_w=2, glow=True):
    """Filled area graph with a gradient under a smooth line, newest on the right."""
    x1, y1, x2, y2 = box
    if len(values) < 2:
        values = list(values or [0.0]) * 2
    n = len(values)
    pts = [(x1 + (x2 - x1) * i / (n - 1), y2 - (y2 - y1) * max(0.0, min(1.0, v)))
           for i, v in enumerate(values)]
    w, h = int(x2 - x1), int(y2 - y1)
    if w <= 0 or h <= 0:
        return
    # Gradient fill: strong under the line, fading to nothing at the bottom.
    shade = Image.new("RGBA", (w, h))
    sd = ImageDraw.Draw(shade)
    for yy in range(h):
        alpha = int(120 * (1 - yy / h) ** 1.6)
        sd.line([(0, yy), (w, yy)], fill=_hex_rgba(color, alpha))
    mask = Image.new("L", (w, h))
    ImageDraw.Draw(mask).polygon([(x - x1, y - y1) for x, y in pts] + [(w, h), (0, h)], fill=255)
    img.paste(shade, (int(x1), int(y1)), Image.composite(shade, Image.new("RGBA", (w, h)), mask).getchannel("A"))
    d.line(pts, fill=_hex_rgba(color), width=line_w * S, joint="curve")
    if glow:
        x, y = pts[-1]
        for r, a in ((7 * S, 60), (4 * S, 255)):
            d.ellipse((x - r, y - r, x + r, y + r), fill=_hex_rgba(color, a))
        d.ellipse((x - 2 * S, y - 2 * S, x + 2 * S, y + 2 * S), fill=_hex_rgba(base_bg))


_wash_cache: dict = {}


def _hero_wash(size, box, color, S):
    """Blurred colour glow in the hero card's corner (cached: the blur is slow)."""
    key = (size, box, color)
    if key not in _wash_cache:
        x1, y1, x2, y2 = box
        wash = Image.new("RGBA", size)
        ImageDraw.Draw(wash).ellipse(((x2 - 120) * S, (y1 - 70) * S, (x2 + 40) * S, (y1 + 70) * S),
                                     fill=_hex_rgba(color, 55))
        wash = wash.filter(ImageFilter.GaussianBlur(26 * S))
        clip = Image.new("L", size)
        ImageDraw.Draw(clip).rounded_rectangle((x1 * S + S, y1 * S + S, x2 * S - 2 * S, y2 * S - 2 * S),
                                               radius=R_PANEL * S, fill=255)
        alpha = Image.composite(wash.getchannel("A"), Image.new("L", size), clip)
        wash.putalpha(alpha)
        _wash_cache.clear()
        _wash_cache[key] = wash
    return _wash_cache[key]


def _render_stats(w, h, hero, cards, cols, card_w, t, corner_r):
    """Whole widget body as one antialiased image, like the media widget."""
    from desktop_widgets.ui.drawing import key_out
    S = SCALE
    # Continue the card underneath (same geometry as BaseWidget's card) so the
    # side and bottom borders stay visible; outside it is keyed transparent.
    img = Image.new("RGBA", (w * S, h * S), _hex_rgba(t.border, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((S, (1 - HDR_H) * S, (w - 1) * S - 1, (h - 1) * S - 1),
                        radius=max(0, corner_r) * S, fill=_hex_rgba(t.bg),
                        outline=_hex_rgba(t.border), width=S)

    def text(x, y, value, size, color, bold=False, anchor="lt"):
        d.text((int(x * S), int(y * S)), value, fill=color,
               font=_font("segoeuib.ttf" if bold else "segoeui.ttf", size * S), anchor=anchor)

    def panel(x1, y1, x2, y2, radius):
        d.rounded_rectangle((x1 * S, y1 * S, x2 * S - 1, y2 * S - 1), radius=radius * S,
                            fill=_hex_rgba(t.btn), outline=_hex_rgba(t.border), width=S)

    # ── Hero ──
    if hero:
        x1, y1, x2, y2 = INSET, INSET, w - INSET, INSET + HERO_H
        panel(x1, y1, x2, y2, R_PANEL)
        # Soft colour wash in the corner, like the media widget's artwork tint.
        img.alpha_composite(_hero_wash(img.size, (x1, y1, x2, y2), hero["color"], S))
        d = ImageDraw.Draw(img)
        d.ellipse(((x1 + 16) * S, (y1 + 17) * S, (x1 + 22) * S, (y1 + 23) * S), fill=_hex_rgba(hero["color"]))
        text(x1 + 28, y1 + 14, hero["label"].upper(), 8, _hex_rgba(t.txt2), bold=True)
        text(x1 + 16, y1 + 30, hero["disp"], 28, _hex_rgba(t.txt), bold=True)
        if hero["sub"]:
            text(x2 - 16, y1 + 14, hero["sub"], 9, _hex_rgba(t.txt2), anchor="rt")
        chart = ((x1 + 16) * S, (y1 + 74) * S, (x2 - 20) * S, (y2 - 14) * S)
        for k in (0.0, 0.5, 1.0):   # faint guide lines
            gy = chart[1] + (chart[3] - chart[1]) * k
            d.line(((x1 + 16) * S, gy, (x2 - 16) * S, gy), fill=_hex_rgba(t.border, 120), width=S)
        _area_chart(img, d, chart, hero["history"], hero["color"], t.btn, S, line_w=2)
        top = y2 + GAP
    else:
        top = INSET

    # ── Cards ──
    for i, c in enumerate(cards):
        col, row = i % cols, i // cols
        cx1 = INSET + col * (card_w + GAP)
        cy1 = top + row * (CARD_H + GAP)
        cx2, cy2 = cx1 + card_w, cy1 + CARD_H
        panel(cx1, cy1, cx2, cy2, R_TILE)
        d.ellipse(((cx1 + 12) * S, (cy1 + 15) * S, (cx1 + 17) * S, (cy1 + 20) * S), fill=_hex_rgba(c["color"]))
        text(cx1 + 22, cy1 + 12, c["label"].upper(), 8, _hex_rgba(t.txt2), bold=True)
        text(cx1 + 12, cy1 + 28, c["disp"], 17, _hex_rgba(t.txt), bold=True)
        if c["sub"] and card_w >= 120:
            text(cx2 - 12, cy1 + 13, c["sub"], 8, _hex_rgba(t.txt2), anchor="rt")
        if c["kind"] == "bar":
            bx1, bx2, by = cx1 + 12, cx2 - 12, cy2 - 16
            track = _lerp_color(t.btn, c["color"], 0.18)
            d.rounded_rectangle((bx1 * S, by * S, bx2 * S, (by + 6) * S), radius=3 * S, fill=_hex_rgba(track))
            fill_x = bx1 + (bx2 - bx1) * max(0.0, min(1.0, c["frac"]))
            if fill_x - bx1 >= 6:
                d.rounded_rectangle((bx1 * S, by * S, fill_x * S, (by + 6) * S), radius=3 * S,
                                    fill=_hex_rgba(c["color"]))
        elif c["kind"] == "spark":
            _area_chart(img, d, ((cx1 + 10) * S, (cy2 - 26) * S, (cx2 - 10) * S, (cy2 - 9) * S),
                        c["history"], c["color"], t.btn, S, line_w=1, glow=False)

    return key_out(img.resize((w, h), Image.LANCZOS))


class _Sample:
    cpu_pct:   float = 0.0
    cpu_temp:  float = 0.0
    ram_pct:   float = 0.0
    ram_used:  float = 0.0
    ram_total: float = 0.0
    gpu_pct:   float = 0.0
    gpu_temp:  float = 0.0
    disk_r:    float = 0.0
    disk_w:    float = 0.0
    net_up:    float = 0.0
    net_down:  float = 0.0
    uptime_s:  int   = 0
    has_gpu:   bool  = False
    has_temp:  bool  = False


class StatsPlusWidget(BaseWidget):
    MIN_H = HDR_H + 2*INSET + HERO_H
    MAX_H = HDR_H + 2*INSET + HERO_H + (CARD_H + GAP) * 11

    def __init__(self, mgr: "Manager") -> None:
        self._sample      = _Sample()
        self._lock        = threading.Lock()
        self._gpu_ok      = False
        self._prev_disk   = None
        self._prev_disk_t = None
        self._prev_net    = None
        self._prev_net_t  = None
        self._running     = True
        self._tile_refs: list = []   # keep ImageTk refs alive
        self._history: dict[str, deque] = {}   # metric -> recent raw values

        cols   = mgr.data.get("statsplus", {}).get("cols", DEF_COLS)
        fixed_w = self._width_for_cols(cols)
        self.MIN_W = fixed_w
        self.MAX_W = fixed_w

        super().__init__(mgr)

        blk = self.mgr.data.get("statsplus", {})
        self.place(
            x=blk.get("x", 460),
            y=blk.get("y", 60),
            w=fixed_w,
            h=self._natural_h(),
            collapsed=blk.get("collapsed", False),
        )
        self.cv.bind("<Button-3>", self._right_click)

        threading.Thread(target=self._check_gpu,  daemon=True).start()
        threading.Thread(target=self._poll_loop,  daemon=True).start()
        self._schedule_redraw()

    @staticmethod
    def _tile_w_for_cols(cols: int) -> int:
        """Width of one metric card for the chosen column count."""
        return {1: 276, 2: 140, 3: 122, 4: 110}.get(max(1, min(4, cols)), 140)

    @classmethod
    def _width_for_cols(cls, cols: int) -> int:
        cols = max(MIN_COLS, min(MAX_COLS, cols))
        return 2*INSET + cols*cls._tile_w_for_cols(cols) + (cols-1)*GAP

    def _visible_metrics(self) -> list[str]:
        has_gpu = getattr(self, "_sample", None) is not None and self._sample.has_gpu
        return [m for m in self._active_metrics()
                if has_gpu or m not in ("gpu_pct", "gpu_temp")]

    def _natural_h(self) -> int:
        """Hero card plus rows of small cards; the widget never clips."""
        n = len(self._visible_metrics())
        if not n:
            return HDR_H + 2*INSET + CARD_H
        rows = -(-(n - 1) // max(1, self._cols()))
        return HDR_H + 2*INSET + HERO_H + rows*(CARD_H + GAP)

    # ── Polling ────────────────────────────────────────────

    def _check_gpu(self) -> None:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
                creationflags=0x08000000)
            if r.returncode == 0:
                self._gpu_ok = True
        except Exception:
            pass

    def _poll_loop(self) -> None:
        while self._running:
            s = _Sample()
            if PSUTIL_OK:
                s.cpu_pct = psutil.cpu_percent(interval=None)
                vm = psutil.virtual_memory()
                s.ram_pct   = vm.percent
                s.ram_used  = vm.used  / 1_073_741_824
                s.ram_total = vm.total / 1_073_741_824
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for key in ("coretemp","k10temp","cpu_thermal","acpitz"):
                            if key in temps:
                                s.cpu_temp = temps[key][0].current
                                s.has_temp = True
                                break
                except Exception:
                    pass
                # Fallback: WMI thermal zone (Windows — psutil sensors_temperatures
                # always returns empty on Windows, so this is the primary path)
                if not s.has_temp:
                    try:
                        import wmi as _wmi
                        w = _wmi.WMI(namespace="root\\wmi")
                        sensors = w.MSAcpi_ThermalZoneTemperature()
                        if sensors:
                            # Convert from tenths of Kelvin to Celsius
                            temps_c = [(s2.CurrentTemperature / 10.0) - 273.15
                                       for s2 in sensors
                                       if s2.CurrentTemperature > 0]
                            if temps_c:
                                s.cpu_temp = max(temps_c)
                                s.has_temp = True
                    except Exception:
                        pass
                # Second fallback: OpenHardwareMonitor/LibreHardwareMonitor WMI
                if not s.has_temp:
                    try:
                        import wmi as _wmi
                        w = _wmi.WMI(namespace="root\\OpenHardwareMonitor")
                        sensors = w.Sensor()
                        cpu_temps = [float(s2.Value) for s2 in sensors
                                     if s2.SensorType == "Temperature"
                                     and "CPU" in s2.Name and "Package" in s2.Name]
                        if not cpu_temps:
                            cpu_temps = [float(s2.Value) for s2 in sensors
                                         if s2.SensorType == "Temperature"
                                         and "CPU" in s2.Name]
                        if cpu_temps:
                            s.cpu_temp = cpu_temps[0]
                            s.has_temp = True
                    except Exception:
                        pass
                try:
                    now_disk = psutil.disk_io_counters()
                    now_t = time.time()
                    if self._prev_disk and self._prev_disk_t:
                        dt = max(now_t - self._prev_disk_t, 0.001)
                        s.disk_r = (now_disk.read_bytes  - self._prev_disk.read_bytes)  / dt / 1_048_576
                        s.disk_w = (now_disk.write_bytes - self._prev_disk.write_bytes) / dt / 1_048_576
                    self._prev_disk = now_disk; self._prev_disk_t = now_t
                except Exception:
                    pass
                try:
                    now_net = psutil.net_io_counters()
                    now_t   = time.time()
                    if self._prev_net and self._prev_net_t:
                        dt = max(now_t - self._prev_net_t, 0.001)
                        s.net_up   = (now_net.bytes_sent - self._prev_net.bytes_sent) / dt / 1_048_576
                        s.net_down = (now_net.bytes_recv - self._prev_net.bytes_recv) / dt / 1_048_576
                    self._prev_net = now_net; self._prev_net_t = now_t
                except Exception:
                    pass
                try:
                    s.uptime_s = int(time.time() - psutil.boot_time())
                except Exception:
                    pass
            if self._gpu_ok:
                try:
                    r = subprocess.run(
                        ["nvidia-smi",
                         "--query-gpu=temperature.gpu,utilization.gpu",
                         "--format=csv,noheader,nounits"],
                        capture_output=True, text=True, timeout=2,
                        creationflags=0x08000000)
                    if r.returncode == 0:
                        parts = r.stdout.strip().split(",")
                        s.gpu_temp = float(parts[0].strip())
                        s.gpu_pct  = float(parts[1].strip())
                        s.has_gpu  = True
                except Exception:
                    pass
            with self._lock:
                self._sample = s
                for key, value in (("cpu_pct", s.cpu_pct), ("cpu_temp", s.cpu_temp),
                                   ("ram_pct", s.ram_pct), ("ram_used", s.ram_used),
                                   ("gpu_pct", s.gpu_pct), ("gpu_temp", s.gpu_temp),
                                   ("disk_r", s.disk_r), ("disk_w", s.disk_w),
                                   ("net_up", s.net_up), ("net_down", s.net_down)):
                    self._history.setdefault(key, deque(maxlen=HISTORY)).append(value)
            time.sleep(1.5)

    def _schedule_redraw(self) -> None:
        if not self._running: return
        self.redraw()
        self.win.after(1500, self._schedule_redraw)

    # ── Theme ──────────────────────────────────────────────

    def _glow(self):
        return None   # the hero card carries the metric's glow

    def _theme(self):
        return config.get_theme(self.mgr.data,
                                self.mgr.data.get("statsplus", {}).get("theme_override"))

    def _cols(self) -> int:
        return self.mgr.data.get("statsplus", {}).get("cols", DEF_COLS)

    def _tile_w(self) -> int:
        return self._tile_w_for_cols(self._cols())

    def _active_metrics(self) -> list[str]:
        return self.mgr.data.get("statsplus", {}).get("metrics", DEFAULT_METRICS)

    # ── Draw ───────────────────────────────────────────────

    def _draw(self) -> None:
        t = self._theme()
        self.paint_header("System stats", meta="Live", meta_on=True)

        if self._collapsed:
            return

        if not PIL_OK:
            self.cv.create_text(self.W//2, self.H//2,
                text="Requires: pip install pillow",
                font=("Segoe UI", 9), fill=t.txt2, anchor="center")
            return

        with self._lock:
            s = self._sample
            history = {k: list(v) for k, v in self._history.items()}

        natural = self._natural_h()
        if natural != self._full_h:
            self._full_h = self.H = natural
            self.win.geometry(f"{self.W}x{self.H}")
            self.cv.config(height=self.H)

        # key: (raw value, scale max or None to auto-scale, display, sub)
        vals = {
            "cpu_pct":  (s.cpu_pct,  100,  f"{s.cpu_pct:.0f}%", None),
            "cpu_temp": (s.cpu_temp, 110,
                         f"{s.cpu_temp:.0f}°C" if s.has_temp else "N/A", None),
            "ram_pct":  (s.ram_pct,  100,  f"{s.ram_pct:.0f}%",
                         f"{s.ram_used:.1f} / {s.ram_total:.0f} GB"),
            "ram_used": (s.ram_used, s.ram_total or 16, f"{s.ram_used:.1f} GB",
                         f"of {s.ram_total:.0f} GB"),
            "gpu_pct":  (s.gpu_pct,  100,  f"{s.gpu_pct:.0f}%",  None),
            "gpu_temp": (s.gpu_temp, 110,  f"{s.gpu_temp:.0f}°C", None),
            "disk_r":   (s.disk_r,   None, self._fmt_mb(s.disk_r) + "/s", None),
            "disk_w":   (s.disk_w,   None, self._fmt_mb(s.disk_w) + "/s", None),
            "net_up":   (s.net_up,   None, self._fmt_mb(s.net_up) + "/s",  None),
            "net_down": (s.net_down, None, self._fmt_mb(s.net_down) + "/s", None),
            "uptime":   (0,          None, self._fmt_uptime(s.uptime_s), "since boot"),
        }
        rate_colors = {"net_down": t.dn_col, "net_up": t.up_col,
                       "disk_r": t.accent, "disk_w": t.warn}
        labels = {k: lbl for k, lbl, *_ in ALL_METRICS}

        items = []
        for key in self._visible_metrics():
            if key not in vals:
                continue
            raw, mx, disp, sub = vals[key]
            past = history.get(key, [])
            scale = mx or max([1.0, raw, *past])          # rates scale to their recent peak
            frac = max(0.0, min(1.0, raw / scale)) if scale else 0.0
            color = (t.accent if key == "uptime" else rate_colors.get(key)
                     or _metric_color(frac, t))
            items.append({
                "label": labels.get(key, key), "disp": disp, "sub": sub,
                "frac": frac, "color": color,
                "history": [v / scale for v in past] if scale else [],
                "kind": "spark" if key in rate_colors else "text" if key == "uptime" else "bar",
            })

        self._tile_refs.clear()
        body = _render_stats(self.W, self.H - HDR_H, items[0] if items else None, items[1:],
                             max(1, self._cols()), self._tile_w(), t,
                             config.get_corner_radius(self.mgr.data))
        photo = ImageTk.PhotoImage(body, master=self.cv)
        self._tile_refs.append(photo)
        self.cv.create_image(0, HDR_H, image=photo, anchor="nw")

    # ── Formatting ─────────────────────────────────────────

    @staticmethod
    def _fmt_mb(mbps: float) -> str:
        if mbps >= 1000: return f"{mbps/1000:.1f}G"
        if mbps >= 1:    return f"{mbps:.1f}M"
        return f"{int(mbps*1024)}K"

    @staticmethod
    def _fmt_uptime(seconds: int) -> str:
        if seconds <= 0: return "—"
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        m = (seconds % 3600) // 60
        if d: return f"{d}d {h}h"
        if h: return f"{h}h {m}m"
        return f"{m}m"

    # ── No horizontal resize ───────────────────────────────

    def _edge(self, x: int, y: int) -> str:
        return ""

    def set_cols(self, cols: int) -> None:
        cols   = max(MIN_COLS, min(MAX_COLS, cols))
        new_w  = self._width_for_cols(cols)
        blk    = self.mgr.data.setdefault("statsplus", {})
        blk["cols"] = cols
        self.W = new_w; self.MIN_W = new_w; self.MAX_W = new_w
        if not self._collapsed:
            self._full_h = self.H = self._natural_h()
        self.win.geometry(f"{new_w}x{self.H}")
        self.cv.config(width=new_w)
        config.save(self.mgr.data)
        self.redraw()

    # ── Persist ────────────────────────────────────────────

    def _save_geometry(self) -> None:
        blk = self.mgr.data.setdefault("statsplus", {})
        blk["x"] = self._win_x(); blk["y"] = self._win_y()
        blk["w"] = self.W;             blk["h"] = self._full_h
        config.save(self.mgr.data)

    def _notify_collapse_change(self) -> None:
        self.mgr.data.setdefault("statsplus", {})["collapsed"] = self._collapsed
        config.save(self.mgr.data)

    def rect(self):
        return (self._win_x(), self._win_y(), self.W, self.H)

    def destroy(self) -> None:
        self._running = False
        super().destroy()

    def _right_click(self, e) -> None:
        self.mgr.root.focus_force()
        m = self.mgr._menu()
        m.add_command(label="Remove",       command=self.mgr.remove_statsplus)
        m.add_separator()
        m.add_command(label="⚙  Settings",  command=self.mgr.open_settings)
        try: m.tk_popup(e.x_root, e.y_root)
        finally: m.grab_release()