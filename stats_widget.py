"""
stats_widget.py — System stats widget.
Shows CPU, RAM, GPU, Disk. Blocky/tech font for numbers.
All metrics refresh every 1.5 seconds.
"""
from __future__ import annotations
import subprocess, threading, time
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


# ── Metric data class ──────────────────────────────────────
class _Sample:
    cpu_pct:  float = 0.0
    cpu_temp: float = 0.0
    ram_pct:  float = 0.0
    gpu_pct:  float = 0.0
    gpu_temp: float = 0.0
    disk_r:   float = 0.0   # MB/s
    disk_w:   float = 0.0
    has_gpu:  bool  = False
    has_temp: bool  = False


class StatsWidget(BaseWidget):
    MIN_W = 200
    MIN_H = HDR_H + 60
    MAX_H = 600

    def __init__(self, mgr: "Manager") -> None:
        self._sample = _Sample()
        self._lock   = threading.Lock()
        self._gpu_ok = False
        self._prev_disk = None
        self._prev_disk_t = None
        self._running = True

        super().__init__(mgr)

        blk = self.mgr.data["stats"]
        self.place(
            x=blk.get("x", 300),
            y=blk.get("y", 60),
            w=blk.get("w", 240),
            h=blk.get("h", 280),
            collapsed=blk.get("collapsed", False),
        )
        self.cv.bind("<Button-3>", self._right_click)

        # Check GPU
        threading.Thread(target=self._check_gpu, daemon=True).start()
        # Start polling loop
        threading.Thread(target=self._poll_loop, daemon=True).start()
        self._schedule_redraw()

    # ── Polling ────────────────────────────────────────────

    def _check_gpu(self) -> None:
        try:
            r = subprocess.run(
                ["nvidia-smi","--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
                creationflags=0x08000000)
            if r.returncode == 0:
                self._gpu_ok = True
        except: pass

    def _poll_loop(self) -> None:
        while self._running:
            s = _Sample()
            if PSUTIL_OK:
                s.cpu_pct = psutil.cpu_percent(interval=None)
                s.ram_pct = psutil.virtual_memory().percent
                # CPU temp
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for key in ("coretemp","k10temp","cpu_thermal","acpitz"):
                            if key in temps:
                                s.cpu_temp = temps[key][0].current
                                s.has_temp = True
                                break
                except: pass
                # Disk
                try:
                    now_disk = psutil.disk_io_counters()
                    now_t = time.time()
                    if self._prev_disk and self._prev_disk_t:
                        dt = max(now_t - self._prev_disk_t, 0.001)
                        s.disk_r = (now_disk.read_bytes  - self._prev_disk.read_bytes)  / dt / 1_048_576
                        s.disk_w = (now_disk.write_bytes - self._prev_disk.write_bytes) / dt / 1_048_576
                    self._prev_disk   = now_disk
                    self._prev_disk_t = now_t
                except: pass
            # GPU
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
                except: pass

            with self._lock:
                self._sample = s
            time.sleep(1.5)

    def _schedule_redraw(self) -> None:
        if self._running:
            self.redraw()
            self.win.after(1500, self._schedule_redraw)

    # ── Theme ──────────────────────────────────────────────

    def _theme(self):
        return config.get_theme(self.mgr.data,
                                self.mgr.data["stats"].get("theme_override"))

    # ── Draw ───────────────────────────────────────────────

    def _draw(self) -> None:
        t = self._theme()
        blk = self.mgr.data["stats"]
        metrics = blk.get("metrics", ["cpu","ram","gpu","disk"])

        self.cv.create_text(self.W // 2, HDR_H // 2,
            text="System", font=("Segoe UI", 9, "bold"),
            fill=t.txt2, anchor="center")

        if self._collapsed:
            return

        with self._lock:
            s = self._sample

        pad = 14
        bw  = self.W - pad * 2
        y   = HDR_H + 12
        sf  = t.stat_font  # blocky/monospace font

        def bar(label, pct, color, val_str):
            nonlocal y
            # Label left, value right
            self.cv.create_text(pad, y, text=label,
                font=("Segoe UI", 8, "bold"), fill=t.txt2, anchor="w")
            self.cv.create_text(self.W - pad, y, text=val_str,
                font=(sf, 10, "bold"), fill=color, anchor="e")
            y += 15
            # Bar track
            self.cv.create_rectangle(pad, y, pad+bw, y+7,
                fill=t.hov, outline="")
            # Bar fill
            fill_w = max(0, int(bw * min(pct, 1.0)))
            if fill_w > 0:
                self.cv.create_rectangle(pad, y, pad+fill_w, y+7,
                    fill=color, outline="")
            y += 12

        def temp_line(label, temp_c):
            nonlocal y
            if temp_c <= 0: return
            if temp_c > 90:   tc = t.danger
            elif temp_c > 70: tc = t.warn
            else:             tc = t.txt2
            self.cv.create_text(pad, y, text=label,
                font=("Segoe UI", 8), fill=t.txt2, anchor="w")
            self.cv.create_text(self.W - pad, y,
                text=f"{temp_c:.0f}°C",
                font=(sf, 10, "bold"), fill=tc, anchor="e")
            y += 16

        def speed_line(label, mbps, color):
            nonlocal y
            if mbps >= 1000:  v = f"{mbps/1000:.1f} GB/s"
            elif mbps >= 1:   v = f"{mbps:.1f} MB/s"
            else:             v = f"{mbps*1024:.0f} KB/s"
            self.cv.create_text(pad, y, text=label,
                font=("Segoe UI", 8), fill=t.txt2, anchor="w")
            self.cv.create_text(self.W - pad, y, text=v,
                font=(sf, 10, "bold"), fill=color, anchor="e")
            y += 16

        def divider():
            nonlocal y
            self.cv.create_line(pad, y, self.W-pad, y, fill=t.border, width=1)
            y += 8

        # CPU
        if "cpu" in metrics:
            pct = s.cpu_pct / 100
            col = t.danger if pct > 0.85 else t.warn if pct > 0.60 else t.ok
            bar("CPU", pct, col, f"{s.cpu_pct:.0f}%")
            if s.has_temp:
                temp_line("  CPU Temp", s.cpu_temp)
            y += 4

        # RAM
        if "ram" in metrics:
            pct = s.ram_pct / 100
            col = t.danger if pct > 0.85 else t.warn if pct > 0.60 else t.ok
            bar("RAM", pct, col, f"{s.ram_pct:.0f}%")
            y += 4

        # GPU
        if "gpu" in metrics and s.has_gpu:
            pct = s.gpu_pct / 100
            col = t.danger if pct > 0.85 else t.warn if pct > 0.60 else t.ok
            bar("GPU", pct, col, f"{s.gpu_pct:.0f}%")
            if s.gpu_temp > 0:
                temp_line("  GPU Temp", s.gpu_temp)
            y += 4

        # Disk
        if "disk" in metrics:
            if y > HDR_H + 20: divider()
            speed_line("Disk R", s.disk_r, t.up_col)
            speed_line("Disk W", s.disk_w, t.dn_col)

    # ── Persist ────────────────────────────────────────────

    def _save_geometry(self) -> None:
        blk = self.mgr.data["stats"]
        blk["x"] = self._win_x(); blk["y"] = self._win_y()
        blk["w"] = self.W; blk["h"] = self._full_h
        config.save(self.mgr.data)

    def _notify_collapse_change(self) -> None:
        self.mgr.data["stats"]["collapsed"] = self._collapsed
        config.save(self.mgr.data)

    def _right_click(self, e) -> None:
        self.mgr.root.focus_force()
        m = self.mgr._menu()
        m.add_command(label="Remove", command=self.mgr.remove_stats)
        try: m.tk_popup(e.x_root, e.y_root)
        finally: m.grab_release()

    def rect(self):
        return (self._win_x(), self._win_y(), self.W, self.H)

    def destroy(self) -> None:
        self._running = False
        super().destroy()