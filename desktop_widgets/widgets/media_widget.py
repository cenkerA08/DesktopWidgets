"""
media_widget.py — Now Playing widget.
PIL-rendered layout: large album art, clean text, progress bar, controls.
Uses Windows WinRT GlobalSystemMediaTransportControls API (pip install winsdk).
"""
from __future__ import annotations
import threading, time, io, os
from typing import TYPE_CHECKING

import tkinter as tk
from desktop_widgets.theme import HDR_H
from desktop_widgets.widgets.base_widget import BaseWidget
import desktop_widgets.config as config

if TYPE_CHECKING:
    from desktop_widgets.manager import Manager

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
W_FIXED  = 360     # fixed widget width
SCALE    = 3       # PIL render scale for antialiasing

# Computed fixed height — must match _render_media layout exactly
_BODY_H  = 328
FIXED_H  = HDR_H + _BODY_H


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


def _layout(w):
    """Body coordinates shared by rendering, seeking and playback hit targets."""
    return {"progress": (24, 209, w-24, 215), "controls_y": 282,
            "controls": {"prev": (w//2-76, 23),
                         "play_pause": (w//2, 30), "next": (w//2+76, 23)}}


def _time_label(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _render_media(w: int, h: int, tr: "_Track", t,
                  corner_r: int, hover=None, available=True) -> "Image.Image":
    """A transparent, antialiased body that leaves the outer card intact."""
    from PIL import ImageOps
    from desktop_widgets.ui.drawing import widget_icon
    S = SCALE
    img = Image.new("RGBA", (w*S, h*S), t.bg)
    d = ImageDraw.Draw(img)
    def box(coords):
        return tuple(int(v*S) for v in coords)
    def text(x, y, value, size, color, bold=False, anchor="lt", max_width=None):
        font = _best_font(value, "segoeuib.ttf" if bold else "segoeui.ttf", size*S)
        if max_width is not None:
            value = _truncate(value, font, int(max_width*S))
        d.text((int(x*S), int(y*S)), value, fill=color, font=font, anchor=anchor)

    active = bool(tr.title) and available
    # A softly blurred colour wash ties the card to the current album artwork.
    hero = box((16, 16, w-16, 188))
    if tr.art_img is not None and active:
        backdrop = ImageOps.fit(tr.art_img.convert('RGBA'),
                                ((w-32)*S, 172*S), method=Image.Resampling.LANCZOS)
        backdrop = backdrop.filter(ImageFilter.GaussianBlur(20*S))
        backdrop = Image.blend(backdrop, Image.new('RGBA', backdrop.size, t.btn), 0.76)
        hero_mask = Image.new('L', backdrop.size)
        ImageDraw.Draw(hero_mask).rounded_rectangle((0, 0, backdrop.width-1,
            backdrop.height-1), radius=18*S, fill=255)
        img.paste(backdrop, (16*S, 16*S), hero_mask)
    else:
        d.rounded_rectangle(hero, radius=18*S, fill=t.btn)
        d.ellipse(box((w-110, -34, w+24, 100)), fill=t.hov)
    art_size = 128
    if tr.art_img is not None and active:
        art = ImageOps.fit(tr.art_img.convert("RGBA"), (art_size*S, art_size*S),
                           method=Image.Resampling.LANCZOS)
    else:
        art = Image.new("RGBA", (art_size*S, art_size*S), t.hov)
        icon = widget_icon('media', t.accent, size=42*S)
        art.alpha_composite(icon, ((art_size*S-icon.width)//2, (art_size*S-icon.height)//2))
    d.rounded_rectangle(box((30, 34, 30+art_size, 34+art_size)),
                        radius=16*S, fill=t.border)
    mask = Image.new("L", art.size)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,art.width-1,art.height-1), radius=15*S, fill=255)
    img.paste(art, (28*S, 30*S), mask)

    tx, tw = 174, w-194
    text(tx, 38, (tr.source or 'NOW PLAYING') if active else 'YOUR SOUNDTRACK',
         9, t.accent, bold=True, max_width=tw)
    title = tr.title if active else ('Ready when you are' if available else 'Media unavailable')
    title_font = _best_font(title, 'segoeuib.ttf', 16*S)
    lines = _wrap(title, title_font, tw*S)
    for i, line in enumerate(lines[:2]):
        if i == 1 and len(lines) > 2:
            line += '…'
        text(tx, 64+i*24, line, 17, t.txt, bold=True, max_width=tw)
    artist = tr.artist or tr.album or 'Unknown artist'
    if not active:
        artist = 'Play something in your music app.' if available else 'Media integration could not start.'
    if active:
        artist_y = 73 + 24*min(2, len(lines)) + 10
        text(tx, artist_y, artist, 11, t.txt2, max_width=tw)
        if tr.album and tr.album != tr.title and tr.album != artist:
            text(tx, artist_y+19, tr.album, 9, t.txt2, max_width=tw)
    else:
        font = _best_font(artist, 'segoeui.ttf', 10*S)
        for i, line in enumerate(_wrap(artist, font, tw*S)[:2]):
            text(tx, 122+i*15, line, 10, t.txt2, max_width=tw)

    d.rounded_rectangle(hero, radius=18*S, outline=t.border, width=S)
    text(24, 194, 'PROGRESS', 8, t.txt2, bold=True)
    d.line(((24*S, 252*S), ((w-24)*S, 252*S)), fill=t.border, width=S)

    layout = _layout(w)
    cy = layout['controls_y']
    ar, ag, ab = _hex(t.accent)
    on_accent = '#10141d' if (ar*299+ag*587+ab*114)/1000 > 160 else '#ffffff'
    for command, (cx, radius) in layout['controls'].items():
        primary = command == 'play_pause'
        fill = t.accent if primary and active else t.hov if hover == command and active else t.btn
        d.ellipse(box((cx-radius, cy-radius, cx+radius, cy+radius)),
                  fill=fill, outline=t.accent if hover == command and active else t.border,
                  width=S if not primary else 2*S)
        color = on_accent if primary and active else t.txt if active else t.txt2
        if command == 'play_pause':
            if tr.playing and active:
                for offset in (-7, 3):
                    d.rounded_rectangle(box((cx+offset, cy-9, cx+offset+4, cy+9)), radius=S, fill=color)
            else:
                d.polygon([(int(x*S),int(y*S)) for x,y in ((cx-5,cy-10),(cx-5,cy+10),(cx+10,cy))], fill=color)
        else:
            sign = -1 if command == 'prev' else 1
            d.polygon([(int(x*S),int(y*S)) for x,y in
                       ((cx-5*sign,cy-7),(cx-5*sign,cy+7),(cx+5*sign,cy))], fill=color)
            d.rounded_rectangle(box((cx+(7 if sign>0 else -9),cy-7,
                                     cx+(9 if sign>0 else -7),cy+7)), radius=S, fill=color)
    # Composite internal antialiasing onto the theme background, then cut only
    # the outer bottom corners. This avoids color-key fringes in light themes.
    mask = Image.new('L', img.size)
    md = ImageDraw.Draw(mask)
    radius = max(0, corner_r-1)*S
    md.rounded_rectangle((S,0,(w-1)*S-1,(h-1)*S-1), radius=radius, fill=255)
    md.rectangle((S,0,(w-1)*S-1,max(0,h*S-radius-2*S)), fill=255)
    img.putalpha(mask)
    return img.resize((w,h), Image.Resampling.LANCZOS)

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
        self._hover_control = None
        self._tick_id = None
        self._dirty = False
        self._last_art_bytes = None

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
                               track.album != old.album or
                               track.source != old.source or
                               track.duration != old.duration or
                               track.playing != old.playing or
                               track.art_img is not old.art_img)
                    self._track = track
                    self._poll_time = time.time()
                    self._dirty = self._dirty or changed
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
                        payload = bytes(buf)
                        if payload != self._last_art_bytes:
                            self._art_img_raw = Image.open(io.BytesIO(payload)).convert("RGBA")
                            self._last_art_bytes = payload
                        tr.art_img = self._art_img_raw
                except Exception:
                    pass
        except Exception:
            pass
        return tr

    def _tick(self) -> None:
        """Called every 500ms — interpolates progress bar between WinRT polls."""
        if not self._running:
            return
        with self._lock:
            dirty = self._dirty
            self._dirty = False
        if dirty:
            self.redraw()
        if not self._collapsed:
            with self._lock:
                tr = self._track
                pt = self._poll_time
            # Only interpolate if playing and we have duration
            if tr.duration > 0 and pt > 0:
                elapsed = max(0, time.time() - pt) if tr.playing else 0
                live_pos = max(0.0, min(1.0,
                    (tr.pos_secs + elapsed) / tr.duration))
                self._draw_progress_only(live_pos)
        self._tick_id = self.win.after(500, self._tick)

    def _draw_progress_only(self, position: float) -> None:
        """Update only the timeline; artwork is retained between polls."""
        from desktop_widgets.ui.drawing import rounded_rect
        if not self._body_photo or self._collapsed:
            return
        t = self._theme()
        x1, y1, x2, y2 = _layout(self.W)['progress']
        y1 += HDR_H
        y2 += HDR_H
        self.cv.delete('prog_tick')
        before = set(self.cv.find_all())
        rounded_rect(self.cv, x1, y1, x2, y2, 3, fill=t.btn_h)
        with self._lock:
            tr = self._track
        known = bool(tr.title) and tr.duration > 0
        fraction = max(0, min(1, position)) if known else 0
        fill_w = int((x2-x1)*fraction)
        if fill_w:
            rounded_rect(self.cv, x1, y1, x1+fill_w, y2, min(3,fill_w/2), fill=t.accent)
        self.cv.create_text(x1, y2+15, text=_time_label(fraction*tr.duration) if known else '—:—',
                            fill=t.txt2, font=('Segoe UI', 9), anchor='w')
        self.cv.create_text(x2, y2+15, text=_time_label(tr.duration) if known else '—:—',
                            fill=t.txt2, font=('Segoe UI', 9), anchor='e')
        for item in set(self.cv.find_all())-before:
            self.cv.addtag_withtag('prog_tick', item)
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
        self._ctrl_hitboxes = {}
        self._prog_hitbox = (0,0,0,0)
        self.cv.create_text(HDR_H+4, HDR_H//2, text='Now playing',
                            font=('Segoe UI', 10, 'bold'), fill=t.txt, anchor='w')
        with self._lock:
            tr = self._track
        if self._collapsed:
            self._pending_cmd = None
            return
        self.cv.create_text(self.W-20, HDR_H//2,
                            text='PLAYING' if tr.playing and tr.title else 'PAUSED' if tr.title else 'READY',
                            font=('Segoe UI', 8), fill=t.accent if tr.playing else t.txt2, anchor='e')
        if not PIL_OK:
            self.cv.create_text(self.W//2, self.H//2, text='Media display unavailable', fill=t.txt2)
            return
        body_img = _render_media(self.W, self.H-HDR_H, tr, t,
                                 config.get_corner_radius(self.mgr.data), self._hover_control, WINSDK_OK)
        self._body_photo = ImageTk.PhotoImage(body_img, master=self.cv)
        self.cv.create_image(0, HDR_H, image=self._body_photo, anchor='nw')
        layout = _layout(self.W)
        if tr.title and WINSDK_OK:
            if tr.duration > 0:
                x1,y1,x2,y2 = layout['progress']
                self._prog_hitbox = (x1,y1+HDR_H,x2,y2+HDR_H)
            cy = HDR_H+layout['controls_y']
            self._ctrl_hitboxes = {cmd: (cx-radius,cy-radius,cx+radius,cy+radius)
                                  for cmd,(cx,radius) in layout['controls'].items()}
        else:
            self._pending_cmd = None
        self._draw_progress_only(tr.position)

    # ── Input ──────────────────────────────────────────────
    def _on_press_extra(self, e) -> None:
        self._pending_cmd = None
        if self._collapsed:
            return
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
        hovered = next((cmd for cmd,(x1,y1,x2,y2) in self._ctrl_hitboxes.items()
                        if x1 <= e.x <= x2 and y1 <= e.y <= y2), None)
        if hovered != self._hover_control:
            self._hover_control = hovered
            # Don't cancel a pending click when the pointer moves over a button.
            pending = self._pending_cmd
            self.redraw()
            self._pending_cmd = pending
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
        if self._tick_id is not None:
            self.win.after_cancel(self._tick_id)
            self._tick_id = None
        super().destroy()
