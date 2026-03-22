"""
media_widget.py — Now Playing widget.
PIL-rendered layout: large album art, clean text, progress bar, controls.
Uses Windows WinRT GlobalSystemMediaTransportControls API (pip install winsdk).
"""
from __future__ import annotations
import threading, time, io, os
from typing import TYPE_CHECKING

import tkinter as tk
from theme import HDR_H
from base_widget import BaseWidget
import config

if TYPE_CHECKING:
    from manager import Manager

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False

WINSDK_OK = False
_winsdk_err = ""
try:
    import asyncio
    import winsdk.windows.media.control as wmc
    import winsdk.windows.storage.streams as wss
    WINSDK_OK = True
except Exception as e:
    _winsdk_err = str(e)

# ── Layout constants ───────────────────────────────────────
W_FIXED  = 320     # fixed widget width
ART_SZ   = 90      # album art size
PAD      = 14      # outer padding
IPIX     = 8       # inner gap between art and text
PROG_H   = 5       # progress bar height
BTN_R    = 18      # control button radius
BTN_GAP  = 54      # gap between button centres
CTRL_PAD = 38      # extra breathing room above controls
SCALE    = 2       # PIL render scale for antialiasing

# Computed fixed height — must match _render_media layout exactly
_BODY_H  = ART_SZ + 8 + PROG_H + CTRL_PAD + BTN_R*2 + PAD
FIXED_H  = HDR_H + PAD + _BODY_H + PAD


class _Track:
    title:    str   = ""
    artist:   str   = ""
    album:    str   = ""
    position: float = 0.0   # 0.0–1.0 fraction at last poll
    duration: float = 0.0   # total seconds (0 = unknown)
    pos_secs: float = 0.0   # absolute seconds at last poll
    playing:  bool  = False
    art_img:  object = None
    source:   str   = ""


def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return (int(c[0:2],16), int(c[2:4],16), int(c[4:6],16))

def _hex_rgba(c: str, a: int = 255) -> tuple:
    c = c.lstrip("#")
    return (int(c[0:2],16), int(c[2:4],16), int(c[4:6],16), a)


# ── CJK-aware font loading ─────────────────────────────────
#
# PIL resolves bare font filenames against C:\Windows\Fonts on Windows.
# However, .ttc (font collection) files contain multiple faces and PIL
# defaults to index 0, which may not carry CJK glyphs.
#
# This implementation:
#   1. Builds an explicit list of (filename, ttc_index) candidates.
#   2. Resolves each against %WINDIR%\Fonts with the full path.
#   3. Validates CJK coverage by measuring a test glyph.
#   4. Caches results to avoid repeated disk access.
#
# All fonts listed ship with Windows 10/11 by default.

_WINFONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

# (filename, ttc_index) — ordered by preference
_CJK_CANDIDATES: list[tuple[str, int]] = [
    ("meiryo.ttc",   0),   # Meiryo — Japanese, Win Vista+
    ("meiryo.ttc",   1),   # Meiryo UI
    ("msyh.ttc",     0),   # Microsoft YaHei — Simplified Chinese, Win 7+
    ("msyh.ttc",     1),   # Microsoft YaHei UI
    ("malgun.ttf",   0),   # Malgun Gothic — Korean, Win 7+
    ("yugothb.ttc",  0),   # Yu Gothic Bold — Japanese, Win 10+
    ("yugothm.ttc",  0),   # Yu Gothic Medium
    ("yugothr.ttc",  0),   # Yu Gothic Regular
    ("simsun.ttc",   0),   # SimSun — Simplified Chinese
    ("gulim.ttc",    0),   # Gulim — Korean
    ("msgothic.ttc", 0),   # MS Gothic — Japanese
    ("msgothic.ttc", 2),   # MS UI Gothic
]

# Test string that exercises JP / CN / KR simultaneously
_CJK_TEST = "あ字한"

# Cache: key → ImageFont or None
_font_cache: dict[tuple, object] = {}


def _load_cjk_candidate(filename: str, size: int, index: int):
    """
    Attempt to load a font by filename (tried both as full Windows path and
    bare name) and verify it actually renders CJK glyphs.
    Returns an ImageFont on success, None on failure.
    """
    for base in (os.path.join(_WINFONTS, filename), filename):
        try:
            f = ImageFont.truetype(base, size, index=index)
            bbox = f.getbbox(_CJK_TEST)
            # A real CJK glyph should be at least ~40% of the font size wide
            if bbox and (bbox[2] - bbox[0]) > size * 0.4:
                return f
        except Exception:
            continue
    return None


def _find_cjk_font(size: int):
    """Return the first available CJK-capable font at the given pixel size."""
    key = ("__cjk__", size)
    if key in _font_cache:
        return _font_cache[key]
    for filename, index in _CJK_CANDIDATES:
        f = _load_cjk_candidate(filename, size, index)
        if f is not None:
            _font_cache[key] = f
            return f
    _font_cache[key] = None
    return None


def _needs_cjk(text: str) -> bool:
    """Return True if the string contains CJK / Hangul / Kana codepoints."""
    for ch in text:
        cp = ord(ch)
        if (0x3000 <= cp <= 0x9FFF    # CJK unified, kana, bopomofo
                or 0xAC00 <= cp <= 0xD7AF    # Hangul syllables
                or 0xF900 <= cp <= 0xFAFF    # CJK compatibility
                or 0x20000 <= cp <= 0x2FA1F):  # CJK extensions B–F
            return True
    return False


def _try_font(name: str, size: int):
    """
    Load a PIL font by filename at the given size, using the Windows font dir.
    Falls back to PIL's default bitmap font if the file cannot be opened.
    Results are cached.
    """
    key = (name, size)
    if key in _font_cache:
        cached = _font_cache[key]
        return cached if cached is not None else ImageFont.load_default()

    for base in (os.path.join(_WINFONTS, name), name):
        try:
            f = ImageFont.truetype(base, size)
            _font_cache[key] = f
            return f
        except Exception:
            continue

    _font_cache[key] = None
    return ImageFont.load_default()


def _best_font(text: str, preferred_name: str, size: int):
    """
    Return the best available font for rendering `text`.
    Switches to a CJK-capable font automatically when the text contains
    Japanese, Chinese, or Korean characters.
    """
    if _needs_cjk(text):
        cjk = _find_cjk_font(size)
        if cjk is not None:
            return cjk
    return _try_font(preferred_name, size)


def _render_media(w: int, h: int, tr: "_Track", t,
                  corner_r: int) -> "Image.Image":
    """
    Render the full media widget body (below header) with PIL at SCALE×size.
    All coordinates are computed explicitly — no arithmetic drift.
    """
    S    = SCALE
    W    = w * S
    H    = h * S
    P    = PAD * S        # outer padding
    GAP  = IPIX * S       # gap between art and text column

    img = Image.new("RGBA", (W, H), _hex_rgba(t.bg))
    d   = ImageDraw.Draw(img)

    acc  = _hex_rgba(t.accent)
    txt  = _hex_rgba(t.txt)
    txt2 = _hex_rgba(t.txt2)
    hov  = _hex_rgba(t.hov)
    bdr  = _hex_rgba(t.border)

    # ── Album art ─────────────────────────────────────────
    art_x = P
    art_y = P
    art_w = ART_SZ * S
    art_h = ART_SZ * S

    if tr.art_img and PIL_OK:
        art = tr.art_img.resize((art_w, art_h), Image.LANCZOS).convert("RGBA")
        mask = Image.new("L", (art_w, art_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, art_w-1, art_h-1], radius=8*S, fill=255)
        img.paste(art, (art_x, art_y), mask)
    else:
        d.rounded_rectangle([art_x, art_y, art_x+art_w-1, art_y+art_h-1],
                             radius=8*S, fill=hov, outline=bdr, width=S)
        nf = _try_font("segoeui.ttf", 28*S)
        d.text((art_x+art_w//2, art_y+art_h//2), "♪",
               fill=txt2, font=nf, anchor="mm")

    # ── Text column ───────────────────────────────────────
    tx  = art_x + art_w + GAP
    t_w = W - tx - P
    ty  = art_y

    if tr.source:
        sf = _try_font("segoeui.ttf", 7*S)
        d.text((tx, ty), tr.source, fill=_hex_rgba(t.accent), font=sf, anchor="lt")
        ty += 11*S

    # Title — auto-switch to CJK font when needed
    title_f = _best_font(tr.title, "segoeuib.ttf", 15*S)
    for line in _wrap(tr.title, title_f, t_w)[:2]:
        d.text((tx, ty), line, fill=txt, font=title_f, anchor="lt")
        ty += 18*S

    ty += 3*S

    # Artist — auto-switch to CJK font when needed
    artist_f = _best_font(tr.artist, "segoeui.ttf", 13*S)
    d.text((tx, ty), tr.artist, fill=txt2, font=artist_f, anchor="lt")
    ty += 17*S

    # Album — auto-switch to CJK font when needed
    if tr.album and tr.album != tr.title:
        alb_f = _best_font(tr.album, "segoeui.ttf", 11*S)
        d.text((tx, ty), _truncate(tr.album, alb_f, t_w),
               fill=_hex_rgba(t.txt2, 160), font=alb_f, anchor="lt")

    # ── Progress bar — sits BELOW the art block ────────────
    prog_y = art_y + art_h + (8 * S)
    prog_h = PROG_H * S
    prog_w = W - P*2
    r_prog = prog_h // 2
    d.rounded_rectangle([P, prog_y, P+prog_w, prog_y+prog_h],
                         radius=r_prog, fill=hov)
    fill_w = max(r_prog*2, int(prog_w * max(0.0, min(1.0, tr.position))))
    d.rounded_rectangle([P, prog_y, P+fill_w, prog_y+prog_h],
                         radius=r_prog, fill=acc)

    # ── Controls ──────────────────────────────────────────
    ctrl_y = prog_y + prog_h + CTRL_PAD * S
    cx_mid = W // 2
    btn_r  = BTN_R * S

    # Determine if accent is light — if so use dark symbol on accent bg
    ar, ag, ab = _hex(t.accent)
    _accent_luminance = (ar * 299 + ag * 587 + ab * 114) / 1000
    _sym_on_accent = (0, 0, 0, 255) if _accent_luminance > 160 else (255, 255, 255, 255)

    def draw_btn(cx, cy, symbol, accent=False, big=False):
        r = int(btn_r * (1.2 if big else 1.0))
        d.ellipse([cx-r, cy-r, cx+r, cy+r],
                  fill=acc if accent else hov,
                  outline=acc if accent else bdr, width=S)
        fs  = int(13*S if big else 11*S)
        bf  = _try_font("seguisym.ttf", fs)
        col = _sym_on_accent if accent else txt2
        d.text((cx, cy), symbol, fill=col, font=bf, anchor="mm")

    gap = BTN_GAP * S
    draw_btn(cx_mid - gap, ctrl_y, "⏮")
    draw_btn(cx_mid,       ctrl_y, "⏸" if tr.playing else "▶", accent=True, big=True)
    draw_btn(cx_mid + gap, ctrl_y, "⏭")

    return img.resize((w, h), Image.LANCZOS)


def _wrap(text: str, font, max_px: int) -> list[str]:
    """Simple word-wrap for PIL text."""
    words = text.split()
    lines = []
    cur   = ""
    for w in words:
        test = (cur + " " + w).strip()
        try:
            bbox = font.getbbox(test)
            wide = bbox[2] - bbox[0]
        except Exception:
            wide = len(test) * 8
        if wide <= max_px:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines or [""]


def _truncate(text: str, font, max_px: int) -> str:
    for i in range(len(text), 0, -1):
        t = text[:i] + ("…" if i < len(text) else "")
        try:
            bbox = font.getbbox(t)
            if bbox[2] - bbox[0] <= max_px:
                return t
        except Exception:
            return text[:max(1, max_px//8)]
    return ""


class MediaWidget(BaseWidget):
    MIN_W = W_FIXED
    MAX_W = W_FIXED
    MIN_H = FIXED_H
    MAX_H = FIXED_H

    def __init__(self, mgr: "Manager") -> None:
        self._track         = _Track()
        self._art_img_raw   = None
        self._lock          = threading.Lock()
        self._running       = True
        self._ctrl_hitboxes: dict = {}
        self._prog_hitbox:  tuple = (0, 0, 0, 0)   # x1,y1,x2,y2 of progress bar
        self._pending_cmd: str | None = None
        self._body_photo    = None   # keep ImageTk alive
        self._poll_time: float = 0.0  # time.time() when last poll completed

        super().__init__(mgr)

        blk = self.mgr.data.get("media", {})
        self.place(
            x=blk.get("x", 100),
            y=blk.get("y", 100),
            w=W_FIXED,
            h=FIXED_H,          # always use computed height, ignore saved h
            collapsed=blk.get("collapsed", False),
        )
        self.cv.bind("<Button-3>", self._right_click)

        if WINSDK_OK:
            threading.Thread(target=self._poll_loop, daemon=True).start()
            self._tick()   # start smooth progress interpolation
        else:
            self.redraw()

    # ── Polling ────────────────────────────────────────────

    def _poll_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self._running:
            try:
                track = loop.run_until_complete(self._fetch())
                with self._lock:
                    old = self._track
                    # Only trigger a full redraw if something meaningful changed
                    changed = (track.title != old.title or
                               track.artist != old.artist or
                               track.playing != old.playing or
                               track.art_img is not old.art_img)
                    self._track = track
                    self._poll_time = time.time()
                if changed:
                    self.win.after(0, self.redraw)
            except Exception:
                pass
            time.sleep(1.0)
        loop.close()

    async def _fetch(self) -> "_Track":
        tr = _Track()
        try:
            mgr_obj = await wmc.GlobalSystemMediaTransportControlsSessionManager\
                               .request_async()
            session = mgr_obj.get_current_session()
            if not session: return tr

            pb = session.get_playback_info()
            tr.playing = (pb.playback_status ==
                wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING)

            raw_src = session.source_app_user_model_id or ""
            # Clean up source: "Spotify.exe" → "Spotify", "com.spotify.client!App" → "Spotify"
            src = raw_src.split("!")[-1] if "!" in raw_src else raw_src
            src = src.replace(".exe","").replace(".EXE","")
            src = src.split(".")[-1] if "." in src else src
            tr.source = src[:20] if src.lower() not in ("app","main","") else ""

            try:
                tl    = session.get_timeline_properties()
                total = tl.end_time.total_seconds()
                pos   = tl.position.total_seconds()
                tr.duration = total
                tr.pos_secs = pos
                tr.position = max(0.0, min(1.0, pos/total)) if total > 0 else 0.0
            except Exception:
                pass

            info = await session.try_get_media_properties_async()
            if info:
                tr.title  = info.title  or ""
                tr.artist = info.artist or ""
                tr.album  = info.album_title or ""
                try:
                    thumb = info.thumbnail
                    if thumb and PIL_OK:
                        stream = await thumb.open_read_async()
                        sz     = stream.size
                        reader = wss.DataReader(stream)
                        await reader.load_async(sz)
                        buf = bytearray(sz)
                        reader.read_bytes(buf)
                        tr.art_img = Image.open(io.BytesIO(bytes(buf))).convert("RGBA")
                except Exception:
                    pass
        except Exception:
            pass
        return tr

    def _tick(self) -> None:
        """Called every 500ms — interpolates progress bar between WinRT polls."""
        if not self._running:
            return
        if not self._collapsed:
            with self._lock:
                tr = self._track
                pt = self._poll_time
            # Only interpolate if playing and we have duration
            if tr.playing and tr.duration > 0 and pt > 0:
                elapsed = time.time() - pt
                live_pos = max(0.0, min(1.0,
                    (tr.pos_secs + elapsed) / tr.duration))
                self._draw_progress_only(live_pos)
        self.win.after(500, self._tick)

    def _draw_progress_only(self, position: float) -> None:
        """Redraw just the progress bar without re-rendering the full PIL image."""
        if not self._body_photo:
            return
        t  = self._theme()
        x1, y1, x2, y2 = self._prog_hitbox
        if x2 <= x1:
            return
        bar_w = x2 - x1
        # Delete previous tick-drawn bar items only (tagged "prog_tick")
        self.cv.delete("prog_tick")
        # Track
        self.cv.create_rectangle(x1, y1, x2, y2,
                                  fill=t.hov, outline="", tags="prog_tick")
        # Fill
        fill_w = max(0, int(bar_w * position))
        if fill_w > 0:
            self.cv.create_rectangle(x1, y1, x1 + fill_w, y2,
                                     fill=t.accent, outline="", tags="prog_tick")

    def _send_command(self, cmd: str) -> None:
        if not WINSDK_OK: return
        async def _run():
            try:
                mgr_obj = await wmc.GlobalSystemMediaTransportControlsSessionManager\
                                   .request_async()
                s = mgr_obj.get_current_session()
                if not s: return
                if cmd == "play_pause": await s.try_toggle_play_pause_async()
                elif cmd == "next":     await s.try_skip_next_async()
                elif cmd == "prev":     await s.try_skip_previous_async()
                elif cmd.startswith("seek:"):
                    import winsdk.windows.foundation as wf
                    frac = float(cmd.split(":")[1])
                    with self._lock:
                        dur = self._track.duration
                    if dur > 0:
                        target_s = frac * dur
                        # TimeSpan in 100-nanosecond ticks
                        ticks = int(target_s * 10_000_000)
                        ts = wf.TimeSpan()
                        ts.duration = ticks
                        await s.try_change_playback_position_async(ticks)
            except Exception: pass
        def _t():
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_run()); loop.close()
        threading.Thread(target=_t, daemon=True).start()

    # ── Theme ──────────────────────────────────────────────

    def _theme(self):
        return config.get_theme(self.mgr.data,
                                self.mgr.data.get("media", {}).get("theme_override"))

    # ── Draw ───────────────────────────────────────────────

    def _draw(self) -> None:
        t = self._theme()
        self.cv.create_text(self.W // 2, HDR_H // 2,
            text="Media", font=("Segoe UI", 9, "bold"),
            fill=t.txt2, anchor="center")

        if self._collapsed:
            return

        if not WINSDK_OK:
            self.cv.create_text(self.W//2, HDR_H + (self.H-HDR_H)//2,
                text=f"pip install winsdk\n({_winsdk_err[:60]})" if _winsdk_err
                     else "pip install winsdk",
                font=("Segoe UI", 9), fill=t.txt2,
                anchor="center", justify="center", width=self.W-28)
            return

        if not PIL_OK:
            self.cv.create_text(self.W//2, HDR_H+(self.H-HDR_H)//2,
                text="pip install pillow",
                font=("Segoe UI", 9), fill=t.txt2, anchor="center")
            return

        with self._lock:
            tr = self._track

        if not tr.title:
            self.cv.create_text(self.W//2, HDR_H+(self.H-HDR_H)//2,
                text="Nothing playing",
                font=("Segoe UI", 10), fill=t.txt2, anchor="center")
            return

        body_h = self.H - HDR_H
        if body_h < 20:
            # Stale saved height — force correct size and redraw next tick
            self._full_h = FIXED_H
            self.H = FIXED_H
            self.win.geometry(f"{self.W}x{FIXED_H}")
            self.cv.config(height=FIXED_H)
            self.win.after(50, self.redraw)
            return
        try:
            body_img = _render_media(self.W, body_h, tr, t,
                                     config.get_corner_radius(self.mgr.data))
            self._body_photo = None          # release old ref before creating new
            self._body_photo = ImageTk.PhotoImage(body_img)
            del body_img                     # free the PIL image immediately
            self.cv.create_image(0, HDR_H, image=self._body_photo, anchor="nw")
        except Exception as e:
            self.cv.create_text(self.W//2, HDR_H+20,
                text=str(e)[:60], font=("Segoe UI", 8), fill=t.danger,
                anchor="n", width=self.W-20)
            return

        # Store progress bar hitbox — must match _render_media prog_y exactly
        prog_y = HDR_H + PAD + ART_SZ + 8
        self._prog_hitbox = (PAD, prog_y, self.W - PAD, prog_y + PROG_H)

        # ctrl_y must match _render_media exactly:
        # PIL: ctrl_y_pil = (PAD + ART_SZ*S + 8*S + PROG_H*S + CTRL_PAD*S)
        # Screen: HDR_H + ctrl_y_pil / SCALE  (ctrl_y IS the button centre)
        S      = SCALE
        ctrl_y = HDR_H + (PAD*S + ART_SZ*S + 8*S + PROG_H*S + CTRL_PAD*S) // S
        cx_mid = self.W // 2
        gap    = BTN_GAP
        br     = BTN_R
        self._ctrl_hitboxes = {
            "prev":       (cx_mid-gap-br, ctrl_y-br, cx_mid-gap+br, ctrl_y+br),
            "play_pause": (cx_mid-int(br*1.2), ctrl_y-int(br*1.2),
                           cx_mid+int(br*1.2), ctrl_y+int(br*1.2)),
            "next":       (cx_mid+gap-br, ctrl_y-br, cx_mid+gap+br, ctrl_y+br),
        }

    # ── Input ──────────────────────────────────────────────

    def _on_press_extra(self, e) -> None:
        if self._mode not in ("", "drag"):
            return

        # Check progress bar click first (seek)
        if self._prog_hitbox:
            x1, y1, x2, y2 = self._prog_hitbox
            # Make the hit zone a bit taller so it's easy to click
            if x1 <= e.x <= x2 and y1 - 6 <= e.y <= y2 + 6:
                bar_w = x2 - x1
                if bar_w > 0:
                    frac = max(0.0, min(1.0, (e.x - x1) / bar_w))
                    self._pending_cmd = f"seek:{frac:.4f}"
                    self._mode = ""
                return

        # Check control buttons
        if not self._ctrl_hitboxes:
            return
        for cmd, (bx1, by1, bx2, by2) in self._ctrl_hitboxes.items():
            if bx1 <= e.x <= bx2 and by1 <= e.y <= by2:
                self._pending_cmd = cmd
                self._mode = ""
                return
        self._pending_cmd = None

    def _on_release_extra(self, e) -> None:
        cmd = getattr(self, "_pending_cmd", None)
        self._pending_cmd = None
        if cmd and not self._moved:
            self._send_command(cmd)

    def _on_cursor(self, e: tk.Event) -> None:
        if e.y <= HDR_H:
            self.cv.config(cursor="hand2" if e.x <= HDR_H else "fleur")
            return
        if self._prog_hitbox:
            x1, y1, x2, y2 = self._prog_hitbox
            if x1 <= e.x <= x2 and y1 - 6 <= e.y <= y2 + 6:
                self.cv.config(cursor="hand2")
                return
        for bx1, by1, bx2, by2 in self._ctrl_hitboxes.values():
            if bx1 <= e.x <= bx2 and by1 <= e.y <= by2:
                self.cv.config(cursor="hand2")
                return
        self.cv.config(cursor="arrow")

    def _right_click(self, e) -> None:
        m = self.mgr._menu()
        m.add_command(label="Remove widget", command=self.mgr.remove_media)
        m.add_separator()
        m.add_command(label="⚙  Settings",   command=self.mgr.open_settings)
        self.mgr.root.focus_force()
        try: m.tk_popup(e.x_root, e.y_root)
        finally: m.grab_release()

    # ── No resize ──────────────────────────────────────────

    def _edge(self, x: int, y: int) -> str:
        return ""

    # ── Persist ────────────────────────────────────────────

    def _save_geometry(self) -> None:
        blk = self.mgr.data.setdefault("media", {})
        blk["x"] = self._win_x()
        blk["y"] = self._win_y()
        blk["w"] = self.W
        # h is not saved — always computed as FIXED_H
        config.save(self.mgr.data)

    def _notify_collapse_change(self) -> None:
        self.mgr.data.setdefault("media", {})["collapsed"] = self._collapsed
        config.save(self.mgr.data)

    def rect(self):
        return (self._win_x(), self._win_y(), self.W, self.H)

    def destroy(self) -> None:
        self._running = False
        super().destroy()