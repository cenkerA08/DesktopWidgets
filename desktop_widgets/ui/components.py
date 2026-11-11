"""Shared Windows 11 style controls for application screens: window shell,
buttons, option cards, navigation items, scrollbars and the theme picker."""
import tkinter as tk
import tkinter.font as tkfont
from desktop_widgets.widgets.base_widget import _rounded_rect
from desktop_widgets.ui.drawing import recolor_shape
from desktop_widgets import theme as th
from desktop_widgets.theme import PRESETS, TYPE, R_WIN, R_CTRL, R_PANEL, mix, on_color


def thin_scrollbar(parent, view, t, bg=None):
    """A slim rounded scrollbar thumb for a Text or Canvas (`view`).
    Returns (canvas, update); call update() after the view scrolls."""
    sb = tk.Canvas(parent, width=8, bg=bg or parent.cget('bg'), highlightthickness=0)
    drag = [None]
    def update(*_):
        try:
            top, bottom = view.yview()
        except tk.TclError:
            return
        sb.delete('thumb')
        h = sb.winfo_height()
        if bottom - top >= 1.0 or h <= 1:
            return
        y1, y2 = max(4, int(top * h)), min(h - 4, int(bottom * h))
        sb.create_line(4, y1 + 2, 4, max(y1 + 3, y2 - 2), width=4, capstyle='round',
                       fill=mix(t.txt2, sb.cget('bg'), 0.45), tags='thumb')
    def press(e): drag[0] = e.y
    def release(e): drag[0] = None
    def move(e):
        if drag[0] is None or sb.winfo_height() <= 1:
            return
        dy = (e.y - drag[0]) / sb.winfo_height()
        drag[0] = e.y
        view.yview_moveto(view.yview()[0] + dy)
        update()
    sb.bind('<ButtonPress-1>', press)
    sb.bind('<B1-Motion>', move)
    sb.bind('<ButtonRelease-1>', release)
    sb.bind('<Configure>', update)
    return sb, update


def release_notes_view(parent, body, theme):
    """Readable headings and bullets without interpreting HTML or remote content."""
    frame = tk.Frame(parent, bg=theme.btn, highlightthickness=1,
                     highlightbackground=theme.border, highlightcolor=theme.border)
    text = tk.Text(frame, wrap='word', bg=theme.btn, fg=theme.txt3,
                   font=TYPE['body'], relief='flat', highlightthickness=0,
                   padx=16, pady=12, height=8, spacing1=2, spacing3=4,
                   cursor='arrow')
    scroll, update = thin_scrollbar(frame, text, theme, bg=theme.btn)
    scroll.pack(side='right', fill='y', padx=(0, 2), pady=4)
    text.pack(fill='both', expand=True)
    text.configure(yscrollcommand=lambda *a: update())
    text.bind('<MouseWheel>', lambda e: (text.yview_scroll(int(-e.delta/120), 'units'), update(), 'break')[-1])
    text.tag_configure('heading', font=TYPE['subtitle'], foreground=theme.txt,
                       spacing1=10, spacing3=6)
    text.tag_configure('bullet', lmargin1=4, lmargin2=20)
    for line in body.splitlines():
        if line.startswith('#'):
            text.insert('end', line.lstrip('#').strip()+'\n', 'heading')
        elif line.startswith(('- ', '* ')):
            text.insert('end', '•   ' + line[2:] + '\n', 'bullet')
        else:
            text.insert('end', line+'\n')
    text.configure(state='disabled')
    return frame


def close_button(cv, x, y, theme, command, size=32):
    """Window close button: a subtle square that turns red on hover."""
    shape = _rounded_rect(cv, x, y, x+size, y+size, R_CTRL, fill=theme.bg)
    cv.addtag_withtag('close', shape)
    mark = cv.create_text(x+size/2, y+size/2, text=th.ICON['close'], fill=theme.txt2,
                          font=(th.ICON_FONT, -11), tags='close')
    cv.tag_bind('close', '<ButtonRelease-1>', lambda e: command())
    # Recolour in place; never recreate items from <Enter>/<Leave>.
    def hover(on):
        cv.config(cursor='hand2' if on else '')
        recolor_shape(cv, shape, '#c42b1c' if on else theme.bg)
        cv.itemconfigure(mark, fill='#ffffff' if on else theme.txt2)
    cv.tag_bind('close', '<Enter>', lambda e: hover(True))
    cv.tag_bind('close', '<Leave>', lambda e: hover(False))


def paint_shell(cv, width, height, theme, title, close, eyebrow='', glows=None, title_y=58):
    """A screen's window: rounded Mica surface, hairline border, a small
    caption above a large title, and a close button in the corner."""
    _rounded_rect(cv, 0, 0, width, height, R_WIN, fill=theme.bg, outline=theme.border, hard=True)
    if eyebrow:
        cv.create_text(28, 30, text=eyebrow, anchor='w', fill=theme.txt2, font=TYPE['caption'])
    cv.create_text(28, title_y if eyebrow else title_y - 16, text=title, anchor='w',
                   fill=theme.txt, font=TYPE['display'])
    close_button(cv, width-44, 12, theme, close)


class RoundedButton(tk.Canvas):
    """Windows 11 button. accent=True is the filled primary button; set_selected
    turns a standard button into a toggled (accent) one."""
    def __init__(self, parent, text, command, theme, accent=False, **kw):
        font = kw.pop('font', TYPE['body'])
        padx, pady = kw.pop('padx', 16), kw.pop('pady', 7)
        icon = kw.pop('icon', None)
        pill = kw.pop('pill', False)
        icon_w = 22 if icon else 0
        measure = tkfont.Font(root=parent, font=font)
        width = kw.pop('width', measure.measure(text)+2*padx+icon_w)
        height = kw.pop('height', measure.metrics('linespace')+2*pady)
        fixed_bg = kw.pop('bg', None)
        fixed_fg = kw.pop('fg', None)
        super().__init__(parent, width=width, height=height,
                         bg=parent.cget('bg'), highlightthickness=0, cursor='hand2', takefocus=True)
        radius = height//2 if pill else R_CTRL
        light = th.is_light(theme)
        state = {'hover': False, 'press': False, 'focus': False}

        def colors():
            if accent:
                base = fixed_bg or theme.accent
                fill = (mix(base, '#000000' if light else '#ffffff', 0.1) if state['hover'] else base)
                if state['press']:
                    fill = mix(base, theme.bg, 0.2)
                return fill, '', fixed_fg or on_color(base)
            fill = fixed_bg or theme.btn
            if state['hover']:
                fill = theme.btn_h
            if state['press']:
                fill = theme.hov
            return fill, theme.border, fixed_fg or theme.txt

        def draw():
            self.delete('all')
            fill, outline, fg = colors()
            _rounded_rect(self, 0, 0, width, height, radius, fill=fill, outline=outline)
            if state['focus'] and not accent:
                _rounded_rect(self, 0, 0, width, height, radius, outline=theme.txt2)
            if icon:
                tw = measure.measure(text)
                x0 = (width - (tw + icon_w))/2
                self.create_text(x0+8, height/2, text=th.ICON.get(icon, icon), fill=fg,
                                 font=(th.ICON_FONT, -12))
                self.create_text(x0+icon_w+tw/2, height/2, text=text, font=font, fill=fg)
            else:
                self.create_text(width/2, height/2, text=text, font=font, fill=fg)

        def set_state(**changes):
            state.update(changes)
            draw()
        draw()
        self.bind('<Enter>', lambda e: set_state(hover=True))
        self.bind('<Leave>', lambda e: set_state(hover=False, press=False))
        self.bind('<ButtonPress-1>', lambda e: set_state(press=True))
        def release(e):
            set_state(press=False)
            if 0 <= e.x <= width and 0 <= e.y <= height:
                command()
        self.bind('<ButtonRelease-1>', release)
        self.bind('<Return>', lambda e: command())
        self.bind('<space>', lambda e: command())
        self.bind('<FocusIn>', lambda e: set_state(focus=True))
        self.bind('<FocusOut>', lambda e: set_state(focus=False))

        def select(selected):
            nonlocal accent
            accent = selected
            draw()
        self.set_selected = select


class NavItem(tk.Canvas):
    """Navigation pane item: icon + label, the selected one gets a subtle fill
    and the accent pill on its left edge."""
    def __init__(self, parent, text, icon, command, theme, selected=False, width=180, height=36):
        super().__init__(parent, width=width, height=height, bg=parent.cget('bg'),
                         highlightthickness=0, cursor='hand2', takefocus=True)
        state = {'hover': False, 'selected': selected}
        def draw():
            self.delete('all')
            if state['selected'] or state['hover']:
                fill = theme.btn if state['selected'] else theme.hov
                _rounded_rect(self, 0, 0, width, height, R_CTRL, fill=fill)
            if state['selected']:
                _rounded_rect(self, 0, height//2-8, 3, height//2+8, 1, fill=theme.accent)
            self.create_text(20, height/2, text=th.ICON.get(icon, icon), anchor='center',
                             fill=theme.txt, font=(th.ICON_FONT, -15))
            self.create_text(42, height/2, text=text, anchor='w', fill=theme.txt, font=TYPE['body'])
        draw()
        def set_state(**changes):
            state.update(changes)
            draw()
        self.bind('<Enter>', lambda e: set_state(hover=True))
        self.bind('<Leave>', lambda e: set_state(hover=False))
        self.bind('<ButtonRelease-1>', lambda e: command())
        self.bind('<Return>', lambda e: command())
        self.set_selected = lambda on: set_state(selected=on)


class OptionButton(tk.Canvas):
    """Radio choice card: a radio circle, a title and a detail line."""
    def __init__(self, parent, title, detail, command, theme, selected=False,
                 width=246, height=64):
        super().__init__(parent, width=width, height=height, bg=parent.cget('bg'),
                         highlightthickness=0, cursor='hand2', takefocus=True)
        def draw(hover=False):
            self.delete('all')
            _rounded_rect(self, 0, 0, width, height, R_CTRL,
                          fill=theme.btn_h if hover else theme.btn,
                          outline=theme.accent if selected else theme.border)
            cx, cy, r = 24, height/2, 9
            if selected:
                self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=theme.accent, outline='')
                self.create_oval(cx-4, cy-4, cx+4, cy+4, fill=on_color(theme.accent), outline='')
            else:
                self.create_oval(cx-r, cy-r, cx+r, cy+r, fill='', outline=theme.txt2, width=1)
            if detail:
                self.create_text(44, height/2-9, text=title, anchor='w', fill=theme.txt,
                                 font=TYPE['body'])
                self.create_text(44, height/2+10, text=detail, anchor='w', fill=theme.txt2,
                                 font=TYPE['caption'], width=width-56)
            else:
                self.create_text(44, height/2, text=title, anchor='w', fill=theme.txt,
                                 font=TYPE['body'])
        draw()
        self.bind('<Enter>', lambda e: draw(True))
        self.bind('<Leave>', lambda e: draw())
        self.bind('<ButtonRelease-1>', lambda e: command())
        self.bind('<Return>', lambda e: command())
        self.bind('<space>', lambda e: command())


def theme_picker(parent, theme, current, on_select, bg=None):
    """Preview thumbnails of every theme, reused for global and per-widget themes."""
    from desktop_widgets.theme import LEGACY_PRESETS
    current = current if current in PRESETS else LEGACY_PRESETS.get(current, current)
    background = bg or theme.bg
    gallery = tk.Frame(parent, bg=background)
    gallery.pack(fill='x')
    cards = []
    W, H = 128, 108
    from desktop_widgets.services import wallpaper
    choices = list(PRESETS.items())
    live = wallpaper.theme()
    if live is not None:
        choices.insert(0, (wallpaper.NAME, live))
    for name, preset in choices:
        chosen = current == name
        cv = tk.Canvas(gallery, width=W, height=H, bg=background,
                       highlightthickness=0, cursor='hand2')
        cards.append(cv)
        cv.grid(row=(len(cards)-1)//4, column=(len(cards)-1) % 4, padx=(0, 10), pady=(0, 6))
        # A small window: its surface, a card with a title line and an accent button.
        _rounded_rect(cv, 0, 0, W, 80, R_PANEL, fill=preset.bg,
                      outline=theme.accent if chosen else preset.border, width=2 if chosen else 1)
        _rounded_rect(cv, 12, 14, W-12, 66, 6, fill=preset.btn, outline=preset.border)
        cv.create_line(22, 28, 64, 28, fill=preset.txt, width=3, capstyle='round')
        cv.create_line(22, 38, 52, 38, fill=preset.txt2, width=3, capstyle='round')
        _rounded_rect(cv, 22, 46, 62, 58, 4, fill=preset.accent)
        _rounded_rect(cv, 68, 46, 98, 58, 4, fill=preset.btn_h, outline=preset.border)
        if chosen:
            cv.create_oval(W-24, 6, W-6, 24, fill=theme.accent, outline='')
            cv.create_text(W-15, 15, text=th.ICON['check'], fill=on_color(theme.accent),
                           font=(th.ICON_FONT, -10))
        if name == wallpaper.NAME:     # mark it as following the wallpaper
            cv.create_text(W-14 if not chosen else W-34, 70, text=th.ICON['picture'], fill=preset.txt2,
                           font=(th.ICON_FONT, -11))
        cv.create_text(2, 95, text='Match wallpaper' if name == wallpaper.NAME else name, anchor='w',
                       fill=theme.txt if chosen else theme.txt3, font=TYPE['caption'])
        cv.bind('<ButtonRelease-1>', lambda e, n=name: on_select(n))
    last_cols = [None]
    def arrange(event):
        cols = max(1, event.width // (W + 10))
        if cols == last_cols[0]:
            return
        last_cols[0] = cols
        for i, card in enumerate(cards):
            card.grid_configure(row=i//cols, column=i % cols)
    gallery.bind('<Configure>', arrange)


class ToggleSwitch(tk.Canvas):
    """Windows 11 toggle switch with its On/Off label on the left."""
    def __init__(self, parent, theme, on, command):
        super().__init__(parent, width=92, height=24, bg=parent.cget('bg'),
                         highlightthickness=0, cursor='hand2', takefocus=True)
        state = {'on': bool(on), 'hover': False}
        def draw():
            self.delete('all')
            x1, y1, x2, y2 = 52, 2, 92, 22
            if state['on']:
                fill = mix(theme.accent, '#ffffff' if not th.is_light(theme) else '#000000',
                           0.1 if state['hover'] else 0)
                _rounded_rect(self, x1, y1, x2, y2, 10, fill=fill)
                knob, kc, kr = x2 - 10, on_color(theme.accent), 5
            else:
                _rounded_rect(self, x1, y1, x2, y2, 10,
                              fill=theme.btn_h if state['hover'] else theme.btn, outline=theme.txt2)
                knob, kc, kr = x1 + 10, theme.txt2, 5
            self.create_oval(knob-kr, 12-kr, knob+kr, 12+kr, fill=kc, outline='')
            self.create_text(42, 12, text='On' if state['on'] else 'Off', anchor='e',
                             fill=theme.txt, font=TYPE['body'])
        def flip(e=None):
            state['on'] = not state['on']
            draw()
            command(state['on'])
        self.bind('<Enter>', lambda e: (state.update(hover=True), draw()))
        self.bind('<Leave>', lambda e: (state.update(hover=False), draw()))
        self.bind('<ButtonRelease-1>', flip)
        self.bind('<space>', flip)
        draw()


def stepper(parent, t, get_val, set_val, min_val=1, max_val=12):
    """Number box with − and + halves (click either side to step)."""
    W, H = 104, 32
    cv = tk.Canvas(parent, width=W, height=H, bg=parent.cget('bg'),
                   highlightthickness=0, cursor='hand2')
    def draw(hover=None):
        cv.delete('all')
        _rounded_rect(cv, 0, 0, W, H, R_CTRL, fill=t.btn, outline=t.border)
        for side, x1, x2 in (('left', 1, 33), ('right', W-33, W-1)):
            if hover == side:
                _rounded_rect(cv, x1+2, 3, x2-2, H-3, 4, fill=t.btn_h)
        cv.create_text(17, H//2, text='', font=(th.ICON_FONT, -11),
                       fill=t.txt if hover == 'left' else t.txt2)
        cv.create_text(W-17, H//2, text=th.ICON['add'], font=(th.ICON_FONT, -11),
                       fill=t.txt if hover == 'right' else t.txt2)
        cv.create_text(W//2, H//2, text=str(get_val()), font=TYPE['strong'], fill=t.txt)
    def side(x):
        return 'left' if x < W//2 else 'right'
    def click(e):
        v = max(min_val, min(max_val, get_val() + (-1 if side(e.x) == 'left' else 1)))
        if v != get_val():
            set_val(v)
        draw(side(e.x))
    # Redraws come from <Motion>/<Button>, never <Enter>, so no hover loop.
    cv.bind('<Motion>', lambda e: draw(side(e.x)))
    cv.bind('<Leave>', lambda e: draw())
    cv.bind('<Button-1>', click)
    draw()
    return cv
