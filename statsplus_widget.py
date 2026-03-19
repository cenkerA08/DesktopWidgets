"""
statsplus_widget.py — Stats+ widget.
Each tile is rendered offscreen with PIL at 2x then downscaled — crisp arcs, no pixelation.
Width fixed by column count. Only collapses, no resize.
"""
from __future__ import annotations
import subprocess, threading, time, math
from typing import TYPE_CHECKING

import tkinter as tk
from theme import HDR_H
from base_widget import BaseWidget
import config

if TYPE_CHECKING:
    from manager import Manager

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
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

TILE_H   = 160
MIN_COLS = 1
MAX_COLS = 4
DEF_COLS = 2
SCALE    = 2      # render at 2x, downscale for antialiasing


def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


def _lerp_color(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    ar, ag, ab = _hex(a); br, bg, bb = _hex(b)
    return "#{:02x}{:02x}{:02x}".format(
        int(ar+(br-ar)*t), int(ag+(bg-ag)*t), int(ab+(bb-ab)*t))


def _metric_color(pct: float, t) -> str:
    if pct < 0.6:
        return _lerp_color(t.ok, t.warn, pct / 0.6)
    return _lerp_color(t.warn, t.danger, (pct - 0.6) / 0.4)


def _hex_rgba(c: str, a: int = 255) -> tuple:
    r, g, b = _hex(c)
    return (r, g, b, a)


def _draw_tile_pil(tile_w: int, tile_h: int,
                   label: str, disp: str, sub: str | None,
                   frac: float, color: str, bg: str, border: str,
                   txt2: str, widget_bg: str,
                   is_uptime: bool = False) -> "Image.Image":
    """
    Render one Stats+ tile at SCALE×size using PIL, return downscaled image.
    widget_bg: the actual widget background color (used to fill the full tile
               so there are no transparent seams between tiles).
    """
    S = SCALE
    W = tile_w * S
    H = tile_h * S
    GAP = 4 * S   # gap around tile edge

    # Start with widget background — no transparent edges
    img = Image.new("RGBA", (W, H), _hex_rgba(widget_bg))
    d   = ImageDraw.Draw(img)

    # Tile card — slightly lighter than widget bg, no border outline
    d.rounded_rectangle([GAP, GAP, W-GAP-1, H-GAP-1],
                         radius=10*S, fill=_hex_rgba(bg))

    # ── Arc ring ───────────────────────────────────────────
    ARC_R  = int(min(tile_w, tile_h) * 0.26 * S)
    arc_cx = W // 2
    arc_cy = int(H * 0.80)
    ARC_W  = max(5*S, int(ARC_R * 0.18))
    START  = 220
    SWEEP  = 260

    # Track — use a mid-brightness color so it's visible but subtle
    def _mid(c: str, bg_c: str, amt: float = 0.25) -> tuple:
        """Blend color toward bg for the track."""
        cr, cg, cb = _hex(c); br, bg_, bb = _hex(bg_c)
        return (int(cr*amt+br*(1-amt)), int(cg*amt+bg_*(1-amt)),
                int(cb*amt+bb*(1-amt)), 255)
    track_col = _mid(color if not is_uptime else txt2, bg, 0.30)

    bbox = [arc_cx-ARC_R, arc_cy-ARC_R, arc_cx+ARC_R, arc_cy+ARC_R]
    d.arc(bbox, start=-START, end=-(START-SWEEP),
          fill=track_col, width=ARC_W)

    # Fill arc
    if not is_uptime and frac > 0.005:
        fill_sweep = int(SWEEP * min(frac, 1.0))
        d.arc(bbox, start=-START, end=-(START-fill_sweep),
              fill=_hex_rgba(color), width=ARC_W)

        # Tip dot with glow
        tip_rad = math.radians(-(START - fill_sweep))
        tip_px  = arc_cx + ARC_R * math.cos(tip_rad)
        tip_py  = arc_cy + ARC_R * math.sin(tip_rad)
        dot_r   = max(4*S, ARC_W // 2 + S)
        d.ellipse([tip_px-dot_r-2*S, tip_py-dot_r-2*S,
                   tip_px+dot_r+2*S, tip_py+dot_r+2*S],
                  fill=_hex_rgba(color, 70))
        d.ellipse([tip_px-dot_r, tip_py-dot_r,
                   tip_px+dot_r, tip_py+dot_r],
                  fill=_hex_rgba(color))

    # ── Label ─────────────────────────────────────────────
    try:    lbl_font = ImageFont.truetype("segoeui.ttf", 9*S)
    except: lbl_font = ImageFont.load_default()
    d.text((W//2, 18*S), label, fill=_hex_rgba(txt2),
           font=lbl_font, anchor="mt")

    # ── Big number ────────────────────────────────────────
    num_y  = int(H * 0.36)
    num_fs = max(22*S, min(32*S, int(tile_w * 0.22 * S)))
    try:    num_font = ImageFont.truetype("segoeuib.ttf", num_fs)
    except:
        try: num_font = ImageFont.truetype("segoeui.ttf", num_fs)
        except: num_font = ImageFont.load_default()
    num_col = _hex_rgba(color) if not is_uptime else _hex_rgba(txt2)
    d.text((W//2, num_y), disp, fill=num_col, font=num_font, anchor="mm")

    # Sub-label
    if sub:
        try:    sub_font = ImageFont.truetype("segoeui.ttf", 7*S)
        except: sub_font = ImageFont.load_default()
        d.text((W//2, num_y + num_fs//2 + 4*S), sub,
               fill=_hex_rgba(txt2), font=sub_font, anchor="mt")

    return img.resize((tile_w, tile_h), Image.LANCZOS)


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
    MIN_H = HDR_H + TILE_H
    MAX_H = HDR_H + TILE_H * 6

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

        cols   = mgr.data.get("statsplus", {}).get("cols", DEF_COLS)
        tile_w = self._tile_w_for_cols(cols)
        fixed_w = tile_w * cols
        self.MIN_W = fixed_w
        self.MAX_W = fixed_w

        super().__init__(mgr)

        blk = self.mgr.data.get("statsplus", {})
        self.place(
            x=blk.get("x", 460),
            y=blk.get("y", 60),
            w=fixed_w,
            h=blk.get("h", HDR_H + TILE_H * 3),
            collapsed=blk.get("collapsed", False),
        )
        self.cv.bind("<Button-3>", self._right_click)

        threading.Thread(target=self._check_gpu,  daemon=True).start()
        threading.Thread(target=self._poll_loop,  daemon=True).start()
        self._schedule_redraw()

    @staticmethod
    def _tile_w_for_cols(cols: int) -> int:
        return {1: 180, 2: 150, 3: 130, 4: 115}.get(max(1, min(4, cols)), 150)

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
            time.sleep(1.5)

    def _schedule_redraw(self) -> None:
        if not self._running: return
        self.redraw()
        self.win.after(1500, self._schedule_redraw)

    # ── Theme ──────────────────────────────────────────────

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
        self.cv.create_text(self.W // 2, HDR_H // 2,
            text="Stats+", font=("Segoe UI", 9, "bold"),
            fill=t.txt2, anchor="center")

        if self._collapsed:
            return

        if not PIL_OK:
            self.cv.create_text(self.W//2, self.H//2,
                text="Requires: pip install pillow",
                font=("Segoe UI", 9), fill=t.txt2, anchor="center")
            return

        with self._lock:
            s = self._sample

        cols   = self._cols()
        tile_w = self._tile_w()

        vals = {
            "cpu_pct":  (s.cpu_pct,  100,  f"{s.cpu_pct:.0f}%",
                         None),
            "cpu_temp": (s.cpu_temp, 110,
                         f"{s.cpu_temp:.0f}°" if s.has_temp else "N/A",
                         None),
            "ram_pct":  (s.ram_pct,  100,  f"{s.ram_pct:.0f}%",
                         f"{s.ram_used:.1f}/{s.ram_total:.0f}G"),
            "ram_used": (s.ram_used, s.ram_total or 16, f"{s.ram_used:.1f}G",
                         f"of {s.ram_total:.0f}G"),
            "gpu_pct":  (s.gpu_pct,  100,  f"{s.gpu_pct:.0f}%",  None),
            "gpu_temp": (s.gpu_temp, 110,  f"{s.gpu_temp:.0f}°", None),
            "disk_r":   (s.disk_r,   None, self._fmt_mb(s.disk_r), None),
            "disk_w":   (s.disk_w,   None, self._fmt_mb(s.disk_w), None),
            "net_up":   (s.net_up,   None, self._fmt_mb(s.net_up),  None),
            "net_down": (s.net_down, None, self._fmt_mb(s.net_down), None),
            "uptime":   (0,          None, self._fmt_uptime(s.uptime_s), None),
        }
        labels = {k: lbl for k, lbl, *_ in ALL_METRICS}

        visible = [m for m in self._active_metrics() if m in vals
                   and (s.has_gpu  or m not in ("gpu_pct",  "gpu_temp"))]

        self._tile_refs.clear()   # release old ImageTk refs before creating new ones

        for i, key in enumerate(visible):
            col = i % cols
            row = i // cols
            ax  = col * tile_w
            ay  = HDR_H + row * TILE_H

            raw, mx, disp, sub = vals[key]
            frac  = max(0.0, min(1.0, (raw / mx) if mx else min(raw / 500, 1.0)))
            color = _metric_color(frac, t) if key != "uptime" else t.txt2

            tile_img = _draw_tile_pil(
                tile_w, TILE_H,
                label=labels.get(key, key),
                disp=disp, sub=sub,
                frac=frac, color=color,
                bg=t.hov, border=t.border, txt2=t.txt2,
                widget_bg=t.bg,
                is_uptime=(key == "uptime"),
            )
            photo = ImageTk.PhotoImage(tile_img)
            self._tile_refs.append(photo)
            self.cv.create_image(ax, ay, image=photo, anchor="nw")

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
        tile_w = self._tile_w_for_cols(cols)
        new_w  = tile_w * cols
        blk    = self.mgr.data.setdefault("statsplus", {})
        blk["cols"] = cols
        self.W = new_w; self.MIN_W = new_w; self.MAX_W = new_w
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