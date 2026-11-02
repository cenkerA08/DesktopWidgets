"""Antialiased, cached canvas shapes; geometry stays in native screen pixels."""
from collections import OrderedDict
from PIL import Image, ImageDraw, ImageTk


def rounded_image(w, h, radius, fill, outline='', border=1, corners='all'):
    scale = 3
    w, h = max(1, int(w)), max(1, int(h))
    r = max(0, min(radius, w/2, h/2))
    image = Image.new('RGBA', (w*scale, h*scale))
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
    return image.resize((w,h), Image.Resampling.LANCZOS)


def rounded_rect(canvas, x1, y1, x2, y2, r, fill='', outline='', width=1, corners='all'):
    cache = getattr(canvas, '_shape_cache', None)
    if cache is None:
        canvas._shape_cache = cache = OrderedDict()
        canvas._shape_refs = {}
    # References for live items survive cache eviction; deleted items are released.
    live = set(canvas.find_all())
    canvas._shape_refs = {i: value for i,value in canvas._shape_refs.items() if i in live}
    key = (int(x2-x1), int(y2-y1), r, fill, outline, width, corners)
    if key not in cache:
        cache[key] = ImageTk.PhotoImage(rounded_image(*key), master=canvas)
        while len(cache) > 12:
            cache.popitem(last=False)
    else:
        cache.move_to_end(key)
    item = canvas.create_image(x1, y1, image=cache[key], anchor='nw')
    canvas._shape_refs[item] = (cache[key], key)
    return item


def recolor_shape(canvas, item, fill):
    entry = getattr(canvas, '_shape_refs', {}).get(item)
    if not entry:
        return
    _, key = entry
    updated = (*key[:3], fill, *key[4:])
    cache = canvas._shape_cache
    if updated not in cache:
        cache[updated] = ImageTk.PhotoImage(rounded_image(*updated), master=canvas)
        while len(cache) > 12:
            cache.popitem(last=False)
    canvas.itemconfigure(item, image=cache[updated])
    canvas._shape_refs[item] = (cache[updated], updated)


def glyph_image(kind, color, size):
    """Small antialiased UI glyphs: chevron_down, chevron_right, plus."""
    scale = 4
    s = size*scale
    image = Image.new('RGBA', (s, s))
    draw = ImageDraw.Draw(image)
    width = max(2*scale, int(s*0.13))
    pts = {'chevron_down':  [(0.28, 0.40), (0.50, 0.62), (0.72, 0.40)],
           'chevron_right': [(0.40, 0.28), (0.62, 0.50), (0.40, 0.72)]}.get(kind)
    if pts:
        draw.line([(x*s, y*s) for x, y in pts], fill=color, width=width, joint='curve')
        for x, y in (pts[0], pts[-1]):
            r = width/2
            draw.ellipse((x*s-r, y*s-r, x*s+r, y*s+r), fill=color)
    elif kind == 'plus':
        for box in ((0.26, 0.50, 0.74, 0.50), (0.50, 0.26, 0.50, 0.74)):
            draw.line([(box[0]*s, box[1]*s), (box[2]*s, box[3]*s)], fill=color, width=width)
        r = width/2
        for x, y in ((0.26, 0.5), (0.74, 0.5), (0.5, 0.26), (0.5, 0.74)):
            draw.ellipse((x*s-r, y*s-r, x*s+r, y*s+r), fill=color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def glyph(canvas, x, y, kind, color, size=16, tags=()):
    """Place a cached glyph centred on (x, y)."""
    cache = canvas.__dict__.setdefault('_glyph_cache', {})
    key = (kind, color, size)
    if key not in cache:
        cache[key] = ImageTk.PhotoImage(glyph_image(kind, color, size), master=canvas)
    return canvas.create_image(x, y, image=cache[key], anchor='center', tags=tags)


def widget_icon(kind, color, size=40):
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
