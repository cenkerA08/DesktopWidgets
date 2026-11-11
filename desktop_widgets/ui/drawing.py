"""Antialiased, cached canvas shapes; geometry stays in native screen pixels."""
from collections import OrderedDict
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageTk


def rounded_image(w, h, radius, fill, outline='', border=1, corners='all', hard=False):
    w, h = max(1, int(w)), max(1, int(h))
    r = max(0, min(radius, w/2, h/2))
    # Big panels: only the corners need supersampling. Render a small copy and
    # stretch its flat edges and middle (nine-slice) instead of drawing every
    # pixel at 3x, which made screens with large cards slow to open.
    side = int(2 * (r + border) + 3)
    if w * h > 12000 and w > side + 2 and h > side + 2:
        small = rounded_image(side, side, radius, fill, outline, border, corners)
        c = side // 2
        out = Image.new('RGBA', (w, h))
        def part(box, size, at):
            out.paste(small.crop(box).resize(size, Image.Resampling.NEAREST), at)
        part((0, 0, c, c), (c, c), (0, 0))
        part((c + 1, 0, side, c), (side - c - 1, c), (w - side + c + 1, 0))
        part((0, c + 1, c, side), (c, side - c - 1), (0, h - side + c + 1))
        part((c + 1, c + 1, side, side), (side - c - 1, side - c - 1), (w - side + c + 1, h - side + c + 1))
        part((c, 0, c + 1, c), (w - side + 1, c), (c, 0))                          # top edge
        part((c, c + 1, c + 1, side), (w - side + 1, side - c - 1), (c, h - side + c + 1))  # bottom
        part((0, c, c, c + 1), (c, h - side + 1), (0, c))                          # left edge
        part((c + 1, c, side, c + 1), (side - c - 1, h - side + 1), (w - side + c + 1, c))  # right
        part((c, c, c + 1, c + 1), (w - side + 1, h - side + 1), (c, c))           # middle
        return key_out(out) if hard else out
    scale = 3
    # Transparent pixels carry the edge colour, not black, so downscaling
    # never darkens the antialiased rim.
    edge = outline or fill
    rim = ImageColor.getrgb(edge)[:3] + (0,) if isinstance(edge, str) and edge else (0, 0, 0, 0)
    image = Image.new('RGBA', (w*scale, h*scale), rim)
    draw = ImageDraw.Draw(image)
    def shape(inset, color):
        if not color:
            return
        a, b = inset*scale, inset*scale
        c, d = (w-inset)*scale-1, (h-inset)*scale-1
        rad = max(0, r-inset)*scale
        if c < a or d < b:
            return
        draw.rounded_rectangle((a,b,c,d), radius=rad, fill=color)
        if corners in ('top', 'none'):
            draw.rectangle((a, max(b,d-rad), c,d), fill=color)
        if corners in ('bottom', 'none'):
            draw.rectangle((a,b,c,min(d,b+rad)), fill=color)
    if outline and border:
        shape(0, outline)
        shape(border, fill or (0,0,0,0))
    else:
        shape(0, fill)
    # reduce() averages each 3x3 block: the same smooth edge as LANCZOS for
    # flat shapes, at a fraction of the cost.
    image = image.reduce(scale)
    return key_out(image) if hard else image


def card(canvas, x, y, w, h, r, fill, outline, band_fill=None, band_h=0, glow=None):
    """A widget's outer card as one keyed-out image: one flat surface with a
    hairline border (Windows 11 has no header band and no glow)."""
    cache = canvas.__dict__.setdefault('_card_cache', {})
    key = (int(w), int(h), r, fill, outline)
    if key not in cache:
        cache.clear()           # one live card per canvas
        cache[key] = ImageTk.PhotoImage(key_out(rounded_image(w, h, r, fill, outline)), master=canvas)
    return canvas.create_image(x, y, image=cache[key], anchor='nw')


_shell_base: dict = {}


def soft_glow(w, h, shapes, blur):
    """Blurred colour light at full size, rendered at 1/8 resolution: a soft
    glow looks the same and costs a fraction of a full-size blur.
    shapes: [(color, alpha, (x1, y1, x2, y2)), ...] in full-size pixels."""
    from PIL import ImageFilter
    k = 8
    small = Image.new('RGBA', (max(1, w // k), max(1, h // k)))
    draw = ImageDraw.Draw(small)
    for color, alpha, (x1, y1, x2, y2) in shapes:
        draw.ellipse((x1 / k, y1 / k, x2 / k, y2 / k), fill=ImageColor.getrgb(color)[:3] + (alpha,))
    small = small.filter(ImageFilter.GaussianBlur(max(1, blur / k)))
    return small.resize((w, h), Image.BILINEAR)


def corner_glow(w, h, color, top=0, strength=42):
    """The shared corner light: sized to the surface so small widgets get a
    hint of colour, not a flood."""
    size = min(240, w * 0.7)
    return soft_glow(w, h, [(color, strength,
                             (w - size * 0.8, top - size * 0.55, w + size * 0.35, top + size * 0.5))],
                     size * 0.22)


def panel_image(canvas, w, h, r, fill, outline, base, glow=None):
    """An inset panel drawn over `base` colour, optionally with the corner glow."""
    cache = canvas.__dict__.setdefault('_panel_cache', {})
    key = (int(w), int(h), r, fill, outline, base, glow)
    if key not in cache:
        # Transparent around the rounded corners: panels sit on the card, so
        # whatever is underneath (the corner glow) shows through cleanly.
        image = Image.new('RGBA', (int(w), int(h)), ImageColor.getrgb(outline)[:3] + (0,))
        image.alpha_composite(rounded_image(w, h, r, fill, outline))
        cache.clear()
        cache[key] = ImageTk.PhotoImage(image, master=canvas)
    return cache[key]


def shell_image(canvas, w, h, r, fill, outline, glows):
    """Screen background with soft colour glows along the top, keyed corners.
    glows: [(color, centre_x_fraction), ...]. Each folder's version is kept."""
    cache = canvas.__dict__.setdefault('_shell_cache', OrderedDict())
    key = (w, h, r, fill, outline, tuple(glows))
    if key not in cache:
        base_key = (w, h, r, fill, outline)
        if base_key not in _shell_base:
            _shell_base.clear()
            _shell_base[base_key] = rounded_image(w, h, r, fill, outline)
        base = _shell_base[base_key].copy()
        light = soft_glow(w, h, [(color, 105, (w*fx - 190, -150, w*fx + 190, 95))
                                 for color, fx in glows], 48)
        inner = Image.new('L', (w, h))
        ImageDraw.Draw(inner).rounded_rectangle((2, 2, w-3, h-3), radius=max(0, r-1), fill=255)
        light.putalpha(Image.composite(light.getchannel('A'), Image.new('L', (w, h)), inner))
        base.alpha_composite(light)
        cache[key] = ImageTk.PhotoImage(key_out(base), master=canvas)
        while len(cache) > 12:
            cache.popitem(last=False)
    cache.move_to_end(key)
    return canvas.create_image(0, 0, image=cache[key], anchor='nw')


def key_out(image):
    """Make a window's outer silhouette safe for colour-key transparency.

    Windows only hides pixels that are exactly the key colour. A half-
    transparent edge pixel blends with the near-black key and shows as a dark
    fringe, and Tk even darkens fully transparent pixels by one step when it
    draws them (#010203 -> #000102). So: solid edge, and the outside painted
    with the exact key colour, fully opaque.
    """
    from desktop_widgets.theme import CHROMA
    solid = image.getchannel('A').point(lambda a: 255 if a >= 128 else 0)
    keyed = Image.new('RGBA', image.size, ImageColor.getrgb(CHROMA) + (255,))
    keyed.paste(image.convert('RGB'), (0, 0), solid)
    return keyed


_SHAPES_MAX = 600


def root_cache(widget, name):
    """A cache stored on the Tk root itself, shared by all its windows. It dies
    with that root, so images never leak into a later Tk instance."""
    return widget._root().__dict__.setdefault(name, OrderedDict())


def _shape_photo(canvas, key):
    """Rendered shape for `key`; each distinct shape is drawn once per app run."""
    shapes = root_cache(canvas, '_dw_shapes')
    photo = shapes.get(key)
    if photo is None:
        photo = ImageTk.PhotoImage(rounded_image(*key), master=canvas._root())
        shapes[key] = photo
        while len(shapes) > _SHAPES_MAX:
            shapes.popitem(last=False)
    else:
        shapes.move_to_end(key)
    return photo


def rounded_rect(canvas, x1, y1, x2, y2, r, fill='', outline='', width=1, corners='all',
                 hard=False):
    """hard=True for a window's outer silhouette drawn over the transparent key."""
    refs = canvas.__dict__.setdefault('_shape_refs', {})
    if len(refs) > 64:   # release images of deleted items now and then, not on every call
        live = set(canvas.find_all())
        for item in [i for i in refs if i not in live]:
            del refs[item]
    key = (int(x2-x1), int(y2-y1), r, fill, outline, width, corners, hard)
    photo = _shape_photo(canvas, key)
    item = canvas.create_image(x1, y1, image=photo, anchor='nw')
    refs[item] = (photo, key)   # keeps the image alive even if the cache drops it
    return item


def recolor_shape(canvas, item, fill):
    entry = getattr(canvas, '_shape_refs', {}).get(item)
    if not entry:
        return
    _, key = entry
    updated = (*key[:3], fill, *key[4:])
    photo = _shape_photo(canvas, updated)
    canvas.itemconfigure(item, image=photo)
    canvas._shape_refs[item] = (photo, updated)


def glyph(canvas, x, y, kind, color, size=16, tags=()):
    """A Segoe Fluent Icons glyph centred on (x, y); size is in pixels."""
    from desktop_widgets import theme
    name = {'plus': 'add'}.get(kind, kind)
    return canvas.create_text(x, y, text=theme.ICON.get(name, name), fill=color,
                              font=(theme.ICON_FONT, -int(size)), anchor='center', tags=tags)


_WIDGET_GLYPH = {'folder': 'folder', 'docs': 'document', 'notes': 'note',
                 'statsplus': 'stats', 'media': 'music', 'stack': 'stack'}


def icon_glyph_image(name, color, size):
    """A Fluent icon glyph rendered with PIL (for off-screen images)."""
    import os
    from PIL import ImageFont
    from desktop_widgets import theme
    char = theme.ICON.get(name, name)
    fonts = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    S = 3
    for file in (theme.PIL_ICONS, 'SegoeIcons.ttf', 'segmdl2.ttf'):
        try:
            font = ImageFont.truetype(os.path.join(fonts, file), int(size * S))
            break
        except OSError:
            font = None
    if font is None:
        return None
    image = Image.new('RGBA', (size * S, size * S))
    ImageDraw.Draw(image).text((size * S / 2, size * S / 2), char, fill=color, font=font, anchor='mm')
    return image.resize((size, size), Image.Resampling.LANCZOS)


def widget_icon(kind, color, size=40):
    image = icon_glyph_image(_WIDGET_GLYPH.get(kind, 'music'), color, size)
    if image is not None:
        return image
    scale = 3
    image = Image.new('RGBA', (48*scale, 48*scale))
    draw = ImageDraw.Draw(image)
    def line(points, width=3):
        draw.line([(x*scale,y*scale) for x,y in points], fill=color, width=width*scale, joint='curve')
    def rect(box, radius=3):
        draw.rounded_rectangle(tuple(v*scale for v in box), radius=radius*scale, fill=color)
    if kind == 'folder':
        draw.polygon([(5*scale,12*scale),(20*scale,12*scale),(24*scale,18*scale),(43*scale,18*scale),
                      (43*scale,38*scale),(5*scale,38*scale)], fill=color)
        line([(5,12),(5,9),(19,9),(24,14),(43,14)])
    elif kind in ('docs','notes'):
        line([(32,5),(10,5),(10,42),(38,42),(38,13),(32,5),(32,14),(38,14)], 2)
        for y in (23,29,35):
            line([(17,y),(30 if kind=='docs' else 27,y)], 2)
    elif kind == 'statsplus':
        rect((7,27,14,41),2); rect((20,18,27,41),2); rect((33,7,40,41),2)
    else:
        line([(18,35),(18,12),(38,7),(38,30)],3)
        line([(18,18),(38,13)],3)
        draw.ellipse((6*scale,30*scale,19*scale,40*scale),fill=color)
        draw.ellipse((26*scale,25*scale,39*scale,35*scale),fill=color)
    return image.resize((size,size), Image.Resampling.LANCZOS)
