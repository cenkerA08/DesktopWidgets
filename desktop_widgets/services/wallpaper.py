"""A theme made from the current desktop wallpaper.

Surfaces take a faint tint of the wallpaper's overall colour, the accent is
its most vivid colour (made readable on those surfaces), and bright
wallpapers get a light theme. The result is cached per wallpaper file, and
the manager re-checks every so often so the widgets follow a new wallpaper.
"""
from __future__ import annotations

import colorsys
import ctypes
import os

NAME = "Wallpaper"
_cache: dict = {}


def current_path() -> str | None:
    """The image Windows is showing now. TranscodedWallpaper is the copy
    Windows renders from (also for slideshows); fall back to the set file."""
    themes = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Themes")
    transcoded = os.path.join(themes, "TranscodedWallpaper")
    if os.path.isfile(transcoded) and os.path.getsize(transcoded) > 0:
        return transcoded
    try:
        buf = ctypes.create_unicode_buffer(520)
        ctypes.windll.user32.SystemParametersInfoW(0x73, 520, buf, 0)   # SPI_GETDESKWALLPAPER
        return buf.value if buf.value and os.path.isfile(buf.value) else None
    except Exception:
        return None


def signature() -> tuple | None:
    """Changes whenever the wallpaper changes (path, size and time)."""
    path = current_path()
    if not path:
        return None
    try:
        st = os.stat(path)
        return path, st.st_size, int(st.st_mtime)
    except OSError:
        return None


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in rgb)


def palette(path: str) -> dict:
    """Overall hue/brightness and the most vivid colour of an image."""
    from PIL import Image
    with Image.open(path) as im:
        small = im.convert("RGB").resize((48, 27), Image.Resampling.BILINEAR)
    raw = small.tobytes()
    pixels = [(raw[i] / 255, raw[i + 1] / 255, raw[i + 2] / 255) for i in range(0, len(raw), 3)]
    light = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in pixels) / len(pixels)
    avg = tuple(sum(p[i] for p in pixels) / len(pixels) for i in range(3))
    base_h, _, base_s = colorsys.rgb_to_hls(*avg)
    # Most vivid colour: hue buckets weighted by how much of the image they cover
    # and how saturated they are; ignore near-greys, black and white.
    buckets: dict = {}
    for r, g, b in pixels:
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if s < 0.3 or not 0.15 < l < 0.85:
            continue
        buckets.setdefault(int(h * 18) % 18, []).append((h, l, s))
    best = max(buckets.values(), key=lambda px: len(px) * (sum(p[2] for p in px) / len(px)) ** 2,
               default=None)
    if best:
        accent_h = sum(p[0] for p in best) / len(best)
        accent_s = sum(p[2] for p in best) / len(best)
    else:                              # a grey wallpaper: use its hue, gently
        accent_h, accent_s = base_h, max(0.45, base_s)
    return {"light": light, "hue": base_h, "sat": base_s, "accent_h": accent_h, "accent_s": accent_s}


def build_theme(p: dict):
    from desktop_widgets.theme import _dark, _light
    h, tint = p["hue"], min(0.16, p["sat"] * 0.6)
    acc_s = max(0.55, min(0.9, p["accent_s"]))
    if p["light"] > 0.62:              # bright wallpaper → light widgets
        accent = _hex(colorsys.hls_to_rgb(p["accent_h"], 0.38, acc_s))
        return _light(_hex(colorsys.hls_to_rgb(h, 0.95, tint)), _hex(colorsys.hls_to_rgb(h, 0.985, tint)),
                      accent, txt2=_hex(colorsys.hls_to_rgb(h, 0.38, tint)))
    accent = _hex(colorsys.hls_to_rgb(p["accent_h"], 0.72, acc_s))
    return _dark(_hex(colorsys.hls_to_rgb(h, 0.115, tint)), _hex(colorsys.hls_to_rgb(h, 0.16, tint)),
                 accent, up_col=accent,
                 txt2=_hex(colorsys.hls_to_rgb(h, 0.68, min(0.12, tint))),
                 txt3=_hex(colorsys.hls_to_rgb(h, 0.86, min(0.1, tint))))


def theme():
    """The wallpaper theme, or None when the wallpaper cannot be read."""
    sig = signature()
    if sig is None:
        return None
    if sig not in _cache:
        try:
            _cache.clear()
            _cache[sig] = build_theme(palette(sig[0]))
        except Exception as exc:
            print(f"[wallpaper] {exc}")
            return None
    return _cache[sig]
