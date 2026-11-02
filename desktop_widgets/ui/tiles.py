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

SCALE = 3
_icon_cache: dict[tuple, Image.Image | None] = {}
_tile_cache: OrderedDict = OrderedDict()
_TILE_CACHE_MAX = 256


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


def icon_image(app: dict, size: int, accent: str) -> Image.Image:
    """Best available RGBA icon for an app, normalised to fill `size`."""
    key = (app.get('path'), app.get('icon_path'), app.get('launch'), size)
    if key in _icon_cache:
        return _icon_cache[key] or letter_icon(app.get('name', '?'), size, accent)
    image = None
    try:
        photo = get_icon(app['path'], size, app.get('icon_path'))
        if photo is not None and not getattr(photo, '_letter_tile', False):
            image = ImageTk.getimage(photo).convert('RGBA')
    except Exception:
        image = None
    if image is not None and _content_size(image) < size * 0.75:
        image = _upgrade_small_icon(app, size) or _fill(image, size)
    _icon_cache[key] = image
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


def clear_icon(path: str) -> None:
    for key in [k for k in _icon_cache if k[0] == path]:
        del _icon_cache[key]
    for key in [k for k in _tile_cache if k[0] == path]:
        del _tile_cache[key]


# ── Tiles ──────────────────────────────────────────────────

def tile_photo(master, app: dict, theme, width: int, height: int, icon_size: int,
               icon_y: int, state: str = 'idle', radius: int = 12):
    """A finished tile as a PhotoImage. state: idle | hover | drag | target."""
    key = (app.get('path'), app.get('icon_path'), width, height, icon_size, icon_y, state, radius,
           theme.bg, theme.btn, theme.hov, theme.border, theme.accent, str(master))
    if key in _tile_cache:
        _tile_cache.move_to_end(key)
        return _tile_cache[key]
    S = SCALE
    W, H = width*S, height*S
    image = Image.new('RGBA', (W, H), _rgb(theme.bg) + (255,))
    draw = ImageDraw.Draw(image)
    hover = state in ('hover', 'drag')
    fill = _mix(theme.hov, theme.accent, 0.14) if hover else _rgb(theme.btn)
    if hover:   # soft accent glow behind the lifted tile
        glow = Image.new('RGBA', (W, H))
        ImageDraw.Draw(glow).rounded_rectangle((3*S, 4*S, W-3*S, H-1*S), radius=radius*S,
                                               fill=_rgb(theme.accent) + (70,))
        image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3*S)))
    outline = (_rgb(theme.accent) if state in ('hover', 'drag', 'target')
               else _mix(theme.border, theme.btn, 0.35))
    border = 2*S if state in ('hover', 'drag', 'target') else S
    draw.rounded_rectangle((S, S, W-S-1, H-S-1), radius=radius*S, fill=fill,
                           outline=outline, width=border)
    if state == 'target':
        draw.rounded_rectangle((S*4, S*10, S*7, H-S*10), radius=S*2, fill=_rgb(theme.accent))

    lift = -2 if hover else 0
    size = round(icon_size * (1.08 if hover else 1.0))
    icon = icon_image(app, icon_size*2, theme.accent).resize((size*S, size*S), Image.Resampling.LANCZOS)
    cx, cy = W//2, (icon_y + lift)*S
    shadow = Image.new('RGBA', (W, H))
    shadow_mask = icon.getchannel('A').point(lambda a: a*0.45)
    shadow.paste((0, 0, 0, 255), (cx-icon.width//2, cy-icon.height//2 + 3*S), shadow_mask)
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3*S)))
    image.alpha_composite(icon, (cx-icon.width//2, cy-icon.height//2))

    photo = ImageTk.PhotoImage(image.resize((width, height), Image.Resampling.LANCZOS), master=master)
    _tile_cache[key] = photo
    while len(_tile_cache) > _TILE_CACHE_MAX:
        _tile_cache.popitem(last=False)
    return photo


def fit_label(widget, text: str, font, max_width: int) -> str:
    """Trim to the pixel width actually available, not a fixed character count."""
    import tkinter.font as tkfont
    measure = tkfont.Font(root=widget, font=font).measure
    if measure(text) <= max_width:
        return text
    while text and measure(text.rstrip() + '…') > max_width:
        text = text[:-1]
    return text.rstrip() + '…'
