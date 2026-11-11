"""Auto arrange: tidy layouts for whatever widgets are on a screen.

Every style keeps each widget at its own size and only moves it; nothing
overlaps or leaves the screen, and gaps are even.

Styles
- tidy:      your own arrangement, cleaned up: edges near each other line up,
             widgets near a screen edge sit on it, close gaps become even and
             overlaps are removed
- balanced:  widgets split over the left and right of the screen so both
             sides weigh about the same; the middle stays free
- dashboard: one compact block in the middle, shaped like the screen
- bottom:    centred rows along the bottom, like a dock

Pure planning only: no Tk. Input boxes are {key, x, y, w, h} in screen
pixels; each result is {key: {"x", "y", "rw", "rh"}}.
"""
from __future__ import annotations

GAP = 12          # space between widgets
MARGIN = 24       # space to the screen edges
SNAP = 48         # edges closer than this are treated as meant to line up
EDGE_SNAP = 140   # widgets this close to a screen edge are moved onto it

STYLES = (
    ("tidy", "Tidy up", "Your layout, lined up and evenly spaced"),
    ("balanced", "Balanced", "Split over both sides, middle free"),
    ("dashboard", "Dashboard", "One neat block in the middle"),
    ("bottom", "Bottom dock", "Centred rows along the bottom"),
)


def _result(boxes):
    return {b["key"]: {"x": round(b["x"]), "y": round(b["y"]), "rw": b["w"], "rh": b["h"]} for b in boxes}


def _overlap(a, b, gap=0):
    return (a["x"] < b["x"] + b["w"] + gap and b["x"] < a["x"] + a["w"] + gap and
            a["y"] < b["y"] + b["h"] + gap and b["y"] < a["y"] + a["h"] + gap)


def _clamp(b, area):
    left, top, right, bottom = area
    b["x"] = max(left + MARGIN, min(b["x"], right - MARGIN - b["w"]))
    b["y"] = max(top + MARGIN, min(b["y"], bottom - MARGIN - b["h"]))


def _cluster(values, tolerance):
    """Groups of indexes whose values lie within `tolerance` of their neighbour."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    groups, current = [], []
    for i in order:
        if current and values[i] - values[current[-1]] > tolerance:
            groups.append(current)
            current = []
        current.append(i)
    if current:
        groups.append(current)
    return groups


# ── Tidy up ────────────────────────────────────────────────

def _tidy(boxes, area):
    left, top, right, bottom = area
    for b in boxes:
        _clamp(b, area)
        b["anchor_r"] = right - (b["x"] + b["w"]) < EDGE_SNAP and b["x"] - left > EDGE_SNAP
        b["anchor_b"] = bottom - (b["y"] + b["h"]) < EDGE_SNAP and b["y"] - top > EDGE_SNAP
    # Line up edges that are almost in line (left edges, right edges, tops, bottoms).
    for edge in ("left", "right", "top", "bottom"):
        if edge == "left":
            free = [b for b in boxes if not b["anchor_r"]]
            values = [b["x"] for b in free]
        elif edge == "right":
            free = [b for b in boxes if b["anchor_r"]]
            values = [b["x"] + b["w"] for b in free]
        elif edge == "top":
            free = [b for b in boxes if not b["anchor_b"]]
            values = [b["y"] for b in free]
        else:
            free = [b for b in boxes if b["anchor_b"]]
            values = [b["y"] + b["h"] for b in free]
        for group in _cluster(values, SNAP):
            if len(group) < 2:
                continue
            target = (min if edge in ("left", "top") else max)(values[i] for i in group)
            for i in group:
                b = free[i]
                if edge == "left": b["x"] = target
                elif edge == "right": b["x"] = target - b["w"]
                elif edge == "top": b["y"] = target
                else: b["y"] = target - b["h"]
    # Then widgets near a screen edge move onto it (a lined-up row moves together).
    for b in boxes:
        if b["x"] - left < EDGE_SNAP:
            b["x"] = left + MARGIN
        elif b["anchor_r"]:
            b["x"] = right - MARGIN - b["w"]
        if b["y"] - top < EDGE_SNAP:
            b["y"] = top + MARGIN
        elif b["anchor_b"]:
            b["y"] = bottom - MARGIN - b["h"]
    # Even gaps between neighbours that are close (or overlapping).
    for _ in range(3):
        for a in boxes:
            for b in boxes:
                if a is b:
                    continue
                x_overlap = a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                y_overlap = a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]
                if x_overlap and a["y"] <= b["y"]:            # b below a
                    gap = b["y"] - (a["y"] + a["h"])
                    if -a["h"] < gap < SNAP and gap != GAP:
                        if b["anchor_b"] and not a["anchor_b"]:
                            a["y"] = b["y"] - GAP - a["h"]
                        else:
                            b["y"] = a["y"] + a["h"] + GAP
                elif y_overlap and a["x"] <= b["x"]:          # b right of a
                    gap = b["x"] - (a["x"] + a["w"])
                    if -a["w"] < gap < SNAP and gap != GAP:
                        if b["anchor_r"] and not a["anchor_r"]:
                            a["x"] = b["x"] - GAP - a["w"]
                        else:
                            b["x"] = a["x"] + a["w"] + GAP
    for b in boxes:
        _clamp(b, area)
    _settle_overlaps(boxes, area)
    return _result(boxes)


def _settle_overlaps(boxes, area):
    """Last resort: move anything still overlapping to the nearest free spot,
    trying only spots right next to widgets already placed."""
    placed = []
    for b in sorted(boxes, key=lambda b: (b["y"], b["x"])):
        if any(_overlap(b, p, GAP - 1) for p in placed):
            spots = []
            for p in placed:
                spots += [(p["x"] + p["w"] + GAP, p["y"]), (p["x"] - GAP - b["w"], p["y"]),
                          (p["x"], p["y"] + p["h"] + GAP), (p["x"], p["y"] - GAP - b["h"]),
                          (b["x"], p["y"] + p["h"] + GAP), (b["x"], p["y"] - GAP - b["h"]),
                          (p["x"] + p["w"] + GAP, b["y"]), (p["x"] - GAP - b["w"], b["y"])]
            best = None
            for x, y in spots:
                cand = dict(b, x=x, y=y)
                _clamp(cand, area)
                if any(_overlap(cand, p, GAP - 1) for p in placed):
                    continue
                dist = abs(cand["x"] - b["x"]) + abs(cand["y"] - b["y"])
                if best is None or dist < best[0]:
                    best = (dist, cand["x"], cand["y"])
            if best:
                b["x"], b["y"] = best[1], best[2]
        placed.append(b)


# ── Column helpers (balanced) ──────────────────────────────

def _pack_columns(boxes, usable_h, max_columns):
    """Fewest columns (tallest first into the shortest) that fit the height."""
    for k in range(1, max(1, max_columns) + 1):
        cols, totals = [[] for _ in range(k)], [0] * k
        for b in sorted(boxes, key=lambda b: -b["h"]):
            i = totals.index(min(totals))
            totals[i] += (GAP if cols[i] else 0) + b["h"]
            cols[i].append(b)
        if max(totals) <= usable_h or k == max_columns:
            return [c for c in cols if c]
    return [boxes]


def _balanced(boxes, area):
    left, top, right, bottom = area
    usable_h = bottom - top - 2 * MARGIN
    sides = {"left": [], "right": []}
    weight = {"left": 0, "right": 0}
    # Biggest first onto the lighter side; start on the side it already leans to.
    mid = (left + right) / 2
    for b in sorted(boxes, key=lambda b: -(b["w"] * b["h"])):
        lean = "left" if b["x"] + b["w"] / 2 < mid else "right"
        side = lean if weight[lean] <= weight["left" if lean == "right" else "right"] else \
            ("left" if lean == "right" else "right")
        sides[side].append(b)
        weight[side] += b["w"] * b["h"]
    for side, items in sides.items():
        if not items:
            continue
        max_cols = max(1, int((right - left) / 2 // (max(b["w"] for b in items) + GAP)))
        columns = _pack_columns(items, usable_h, max_cols)
        x = left + MARGIN if side == "left" else right - MARGIN
        for column in columns:
            width = max(b["w"] for b in column)
            y = top + MARGIN
            for b in sorted(column, key=lambda b: -b["h"]):
                b["x"] = x if side == "left" else x - b["w"]
                b["y"] = y
                y += b["h"] + GAP
            x = x + width + GAP if side == "left" else x - width - GAP
    for b in boxes:
        _clamp(b, area)
    _settle_overlaps(boxes, area)
    return _result(boxes)


# ── Row helpers (dashboard, bottom) ────────────────────────

def _rows_for(boxes, max_w):
    rows, row, width = [], [], 0
    for b in boxes:
        if row and width + GAP + b["w"] > max_w:
            rows.append(row)
            row, width = [], 0
        width += (GAP if row else 0) + b["w"]
        row.append(b)
    if row:
        rows.append(row)
    return rows


def _row_width(row):
    return sum(b["w"] for b in row) + GAP * (len(row) - 1)


def _rows_height(rows):
    return sum(max(b["h"] for b in r) for r in rows) + GAP * (len(rows) - 1)


def _dashboard(boxes, area):
    left, top, right, bottom = area
    usable_w, usable_h = right - left - 2 * MARGIN, bottom - top - 2 * MARGIN
    ordered = sorted(boxes, key=lambda b: (b["y"] // 200, b["x"]))     # roughly reading order
    screen_ratio = usable_w / max(1, usable_h)
    best = None
    widest = max(b["w"] for b in boxes)
    for target in range(widest, usable_w + 1, 40):
        rows = _rows_for(ordered, target)
        w = max(_row_width(r) for r in rows)
        h = _rows_height(rows)
        if h > usable_h:
            continue
        score = abs((w / max(1, h)) - screen_ratio)
        if best is None or score < best[0] - 0.01:
            best = (score, rows, w, h)
    if best is None:
        rows = _rows_for(ordered, usable_w)
        best = (0, rows, max(_row_width(r) for r in rows), _rows_height(rows))
    _, rows, w, h = best
    y = top + MARGIN + max(0, (usable_h - h) // 2)
    for row in rows:
        x = left + MARGIN + (usable_w - _row_width(row)) // 2
        for b in row:
            b["x"], b["y"] = x, y
            x += b["w"] + GAP
        y += max(b["h"] for b in row) + GAP
    for b in boxes:
        _clamp(b, area)
    return _result(boxes)


def _bottom(boxes, area):
    left, top, right, bottom = area
    usable_w = right - left - 2 * MARGIN
    rows = _rows_for(sorted(boxes, key=lambda b: b["x"]), usable_w)
    y_bottom = bottom - MARGIN
    for row in reversed(rows):
        x = left + MARGIN + (usable_w - _row_width(row)) // 2
        for b in row:
            b["x"], b["y"] = x, y_bottom - b["h"]
            x += b["w"] + GAP
        y_bottom -= max(b["h"] for b in row) + GAP
    for b in boxes:
        _clamp(b, area)
    _settle_overlaps(boxes, area)
    return _result(boxes)


def plan_style(style: str, area: tuple, boxes: list[dict]) -> dict:
    """Positions for one monitor. boxes: [{key, x, y, w, h}] (widget sizes are kept)."""
    if not boxes:
        return {}
    boxes = [dict(b) for b in boxes]
    if style == "balanced":
        return _balanced(boxes, area)
    if style == "dashboard":
        return _dashboard(boxes, area)
    if style == "bottom":
        return _bottom(boxes, area)
    return _tidy(boxes, area)
