"""App tiles shared by folder widgets and the focus view.

Each tile (background, border, soft shadow and icon) is rendered as one
supersampled PIL image composited onto the widget background, the same way
the media widget draws its body. Labels stay Tk text so they get ClearType.
"""
from __future__ import annotations
import os
import re
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

from desktop_widgets.utils import get_icon
from desktop_widgets.ui.drawing import soft_glow, root_cache

SCALE = 3
_icon_cache: dict[tuple, Image.Image | None] = {}
_TILE_CACHE_MAX = 480


def _rgb(color: str) -> tuple:
    color = color.lstrip('#')
    return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))


def _mix(a: str, b: str, amount: float) -> tuple:
    ar, ag, ab = _rgb(a); br, bg, bb = _rgb(b)
    return (round(ar+(br-ar)*amount), round(ag+(bg-ag)*amount), round(ab+(bb-ab)*amount))


# ── Icons ──────────────────────────────────────────────────

def _steam_game_exe(appid: str) -> str | None:
    """The main executable of an installed Steam game, for its full-size icon."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
            steam = winreg.QueryValueEx(key, 'SteamPath')[0]
        libraries = [steam]
        vdf = os.path.join(steam, 'steamapps', 'libraryfolders.vdf')
        if os.path.isfile(vdf):
            with open(vdf, encoding='utf-8', errors='ignore') as f:
                libraries += [p.replace('\\\\', '\\') for p in re.findall(r'"path"\s+"([^"]+)"', f.read())]
        for library in libraries:
            manifest = os.path.join(library, 'steamapps', f'appmanifest_{appid}.acf')
            if not os.path.isfile(manifest):
                continue
            with open(manifest, encoding='utf-8', errors='ignore') as f:
                found = re.search(r'"installdir"\s+"([^"]+)"', f.read())
            if not found:
                continue
            folder = os.path.join(library, 'steamapps', 'common', found.group(1))
            skip = ('unins', 'crash', 'setup', 'redist', 'report', 'helper', 'dotnet', 'vc_', 'ue4prereq')
            best = None
            for parent, dirs, files in os.walk(folder):
                if parent.count(os.sep) - folder.count(os.sep) >= 3:
                    dirs[:] = []
                for name in files:
                    low = name.lower()
                    if low.endswith('.exe') and not any(s in low for s in skip):
                        path = os.path.join(parent, name)
                        size = os.path.getsize(path)
                        if best is None or size > best[0]:
                            best = (size, path)
            return best[1] if best else None
    except OSError:
        pass
    return None


def _upgrade_small_icon(app: dict, size: int) -> Image.Image | None:
    """Steam ships 32px icons for some games; the game's own .exe is sharper."""
    launch = app.get('launch', '') or ''
    found = re.match(r'steam://rungameid/(\d+)', launch)
    if not found:
        return None
    exe = _steam_game_exe(found.group(1))
    if not exe:
        return None
    photo = get_icon(exe, size)
    image = ImageTk.getimage(photo).convert('RGBA') if photo else None
    return image if image is not None and _content_size(image) >= size * 0.6 else None


def _file_type_icon(app: dict, size: int) -> Image.Image | None:
    """Documents: the high-resolution icon Explorer shows for the file type."""
    path = app.get('path', '')
    if not os.path.isfile(path):
        return None
    from desktop_widgets.utils import _shell_icon
    photo = _shell_icon(path, size)
    return ImageTk.getimage(photo).convert('RGBA') if photo else None


def _content_size(image: Image.Image) -> int:
    box = image.getchannel('A').getbbox()
    return max(box[2]-box[0], box[3]-box[1]) if box else 0


def letter_icon(name: str, size: int, accent: str) -> Image.Image:
    """Fallback artwork: a rounded gradient square with the first letter."""
    s = size * SCALE
    letter = (name.strip()[:1] or '?').upper()
    top, bottom = _mix(accent, '#ffffff', 0.18), _mix(accent, '#000000', 0.28)
    gradient = Image.new('RGBA', (1, s))
    for y in range(s):
        k = y / max(1, s-1)
        gradient.putpixel((0, y), tuple(round(top[i]+(bottom[i]-top[i])*k) for i in range(3)) + (255,))
    gradient = gradient.resize((s, s))
    mask = Image.new('L', (s, s))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s-1, s-1), radius=int(s*0.24), fill=255)
    image = Image.new('RGBA', (s, s))
    image.paste(gradient, (0, 0), mask)
    try:
        font = ImageFont.truetype('segoeuib.ttf', int(s*0.5))
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(image).text((s/2, s/2), letter, fill='white', font=font, anchor='mm')
    return image.resize((size, size), Image.Resampling.LANCZOS)


def _disk_key(app: dict, size: int) -> str:
    """Cache file name; changes when the app, its icon file or launch link change."""
    import hashlib
    stamp = []
    for path in (app.get('path', ''), app.get('icon_path') or ''):
        try:
            stamp.append(str(int(os.path.getmtime(path))))
        except (OSError, ValueError):
            stamp.append('-')
    raw = '|'.join([str(app.get('path')), str(app.get('icon_path')), str(app.get('launch')),
                    str(size), *stamp, 'v1'])
    return hashlib.sha1(raw.encode('utf-8', 'ignore')).hexdigest() + '.png'


def _disk_folder() -> str:
    from desktop_widgets.config import DATA_DIR
    return os.path.join(DATA_DIR, 'icon_cache')


def icon_image(app: dict, size: int, accent: str) -> Image.Image:
    """Best available RGBA icon for an app, normalised to fill `size`.

    Extracting icons from programs is slow (COM/GDI), so results are kept as
    small PNGs on disk and the next start reads those instead."""
    key = (app.get('path'), app.get('icon_path'), app.get('launch'), size)
    if key in _icon_cache:
        return _icon_cache[key] or letter_icon(app.get('name', '?'), size, accent)
    cached = os.path.join(_disk_folder(), _disk_key(app, size))
    try:
        with Image.open(cached) as stored:
            _icon_cache[key] = stored.convert('RGBA')
        return _icon_cache[key]
    except OSError:
        pass
    image = None
    try:
        photo = get_icon(app['path'], size, app.get('icon_path'))
        if photo is not None and not getattr(photo, '_letter_tile', False):
            image = ImageTk.getimage(photo).convert('RGBA')
    except Exception:
        image = None
    if image is None:          # no icon found: a Steam game's own .exe still has one,
        image = _upgrade_small_icon(app, size) or _file_type_icon(app, size)   # files their app's
    elif _content_size(image) < size * 0.75:
        image = _upgrade_small_icon(app, size) or _fill(image, size)
    _icon_cache[key] = image
    if image is not None:
        try:
            os.makedirs(_disk_folder(), exist_ok=True)
            image.save(cached, 'PNG')
        except OSError:
            pass
    return image or letter_icon(app.get('name', '?'), size, accent)


def _fill(image: Image.Image, size: int) -> Image.Image:
    """Scale a small icon's visible content up to the common size."""
    box = image.getchannel('A').getbbox()
    if not box:
        return image
    content = image.crop(box)
    scale = (size * 0.86) / max(content.size)
    content = content.resize((max(1, round(content.width*scale)), max(1, round(content.height*scale))),
                             Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (size, size))
    canvas.alpha_composite(content, ((size-content.width)//2, (size-content.height)//2))
    return canvas


_color_cache: dict[tuple, str] = {}


def icon_color(app: dict, fallback: str) -> str:
    """The icon's most vivid colour, for tinting its tile and the focus view."""
    import colorsys
    key = (app.get('path'), app.get('icon_path'))
    if key not in _color_cache:
        small = icon_image(app, 48, fallback).resize((16, 16), Image.Resampling.BILINEAR)
        best, score = None, 0.0
        buckets: dict[int, list] = {}
        for r, g, b, a in small.getdata():
            if a < 160:
                continue
            h, l, sat = colorsys.rgb_to_hls(r/255, g/255, b/255)
            if sat < 0.25 or not 0.18 < l < 0.85:
                continue                      # skip greys, black and white
            buckets.setdefault(int(h*12) % 12, []).append((r, g, b, sat))
        for pixels in buckets.values():
            weight = len(pixels) * sum(p[3] for p in pixels) / len(pixels)
            if weight > score:
                n = len(pixels)
                best = '#%02x%02x%02x' % tuple(sum(p[i] for p in pixels)//n for i in range(3))
                score = weight
        _color_cache[key] = best or fallback
    return _color_cache[key]


def clear_icon(path: str) -> None:
    for key in [k for k in _icon_cache if k[0] == path]:
        del _icon_cache[key]
    for key in [k for k in _color_cache if k[0] == path]:
        del _color_cache[key]


# ── Tiles ──────────────────────────────────────────────────

def tile_photo(master, app: dict, theme, width: int, height: int, icon_size: int,
               icon_y: int, state: str = 'idle', radius: int = 12, tint: str | None = None,
               transparent: bool = False):
    """A finished tile as a PhotoImage. state: idle | hover | drag | target.
    tint: the icon's own colour, washed into the tile behind the icon.
    transparent: rounded corners show what is underneath (the widget's glow)."""
    key = (app.get('path'), app.get('icon_path'), width, height, icon_size, icon_y, state, radius,
           theme.bg, theme.btn, theme.hov, theme.border, theme.accent, tint, transparent)
    tiles = root_cache(master, '_dw_tiles')
    if key in tiles:
        tiles.move_to_end(key)
        return tiles[key]
    stored = _stored_tile(app, key) if state == 'idle' else None
    if stored is not None:
        photo = ImageTk.PhotoImage(stored, master=master._root())
        _remember(tiles, key, photo)
        return photo
    S = SCALE
    W, H = width*S, height*S
    image = Image.new('RGBA', (W, H), _rgb(theme.btn) + (0,) if transparent else _rgb(theme.bg) + (255,))
    draw = ImageDraw.Draw(image)
    hover = state in ('hover', 'drag')
    selected = state in ('selected', 'selected_hover')
    lifted = hover or state == 'selected_hover'
    fill = _mix(theme.hov, theme.accent, 0.14) if hover or selected else _rgb(theme.btn)
    if hover:   # soft accent glow behind the lifted tile
        image.alpha_composite(soft_glow(W, H, [(theme.accent, 70, (3*S, 4*S, W-3*S, H-S))], 6*S))
    ringed = state in ('hover', 'drag', 'target', 'selected', 'selected_hover')
    outline = _rgb(theme.accent) if ringed else _mix(theme.border, theme.btn, 0.35)
    border = 2*S if ringed else S
    draw.rounded_rectangle((S, S, W-S-1, H-S-1), radius=radius*S, fill=fill,
                           outline=outline, width=border)
    if tint:   # icon-coloured light from the top, stronger on hover
        light = soft_glow(W, H, [(tint, 95 if lifted or selected else 58, (W*0.08, -H*0.55, W*0.92, H*0.62))], 14*S)
        inside = Image.new('L', (W, H))
        ImageDraw.Draw(inside).rounded_rectangle((S*2, S*2, W-S*2-1, H-S*2-1), radius=radius*S, fill=255)
        light.putalpha(Image.composite(light.getchannel('A'), Image.new('L', (W, H)), inside))
        image.alpha_composite(light)
        draw = ImageDraw.Draw(image)
    if state == 'target':
        draw.rounded_rectangle((S*4, S*10, S*7, H-S*10), radius=S*2, fill=_rgb(theme.accent))

    lift = -2 if lifted else 0
    size = round(icon_size * (1.08 if lifted else 1.0))
    icon = icon_image(app, icon_size*2, theme.accent).resize((size*S, size*S), Image.Resampling.LANCZOS)
    cx, cy = W//2, (icon_y + lift)*S
    # Soft drop shadow, blurred at 1x and scaled up (cheap, looks identical).
    shadow = Image.new('RGBA', (W//S, H//S))
    small_icon = icon.getchannel('A').resize((max(1, icon.width//S), max(1, icon.height//S)))
    shadow.paste((0, 0, 0, 255), (cx//S - small_icon.width//2, cy//S - small_icon.height//2 + 3),
                 small_icon.point(lambda a: a*0.45))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR))
    image.alpha_composite(icon, (cx-icon.width//2, cy-icon.height//2))

    # Owned by the Tk root so tiles are reused across windows (focus view reopen).
    final = image.reduce(S)
    if state == 'idle':
        _store_tile(app, key, final)
    photo = ImageTk.PhotoImage(final, master=master._root())
    _remember(tiles, key, photo)
    return photo


def _remember(tiles, key, photo):
    tiles[key] = photo
    while len(tiles) > _TILE_CACHE_MAX:
        tiles.popitem(last=False)


def _tile_file(app, key):
    import hashlib
    raw = repr(key) + _disk_key(app, 0)     # includes the app/icon file timestamps
    return os.path.join(_disk_folder(), 'tile-' + hashlib.sha1(raw.encode('utf-8', 'ignore')).hexdigest() + '.png')


def _stored_tile(app, key):
    try:
        with Image.open(_tile_file(app, key)) as stored:
            return stored.convert('RGBA')
    except OSError:
        return None


def _store_tile(app, key, image):
    try:
        os.makedirs(_disk_folder(), exist_ok=True)
        image.save(_tile_file(app, key), 'PNG')
    except OSError:
        pass


def fit_label(widget, text: str, font, max_width: int) -> str:
    """Trim to the pixel width actually available, not a fixed character count."""
    import tkinter.font as tkfont
    measure = tkfont.Font(root=widget, font=font).measure
    if measure(text) <= max_width:
        return text
    while text and measure(text.rstrip() + '…') > max_width:
        text = text[:-1]
    return text.rstrip() + '…'
