"""Element builders for authoring .excalidraw JSON architecture plots.

Usage: copy into a scratch dir, build a scene as a list of elements, save(), then
render via kroki + preview via qlmanage (see references/excalidraw-plots.md).

CRITICAL: every coordinate/size must be a NUMBER. One string x/y NaN-poisons the
whole scene's bounding box and every element renders at (0,0).
"""

import json

# Excalidraw standard palette. Pick ONE semantic axis per figure (role OR tier)
# and keep it consistent; print a legend when the figure uses >3 colors.
# Role semantics (Awesome-ML-SYS-Tutorial house style):
#   green=procedure/function  blue=engine/component  yellow=data object
#   pink=network/resource     purple=queue/state     gray=replica/misc
# Tier semantics (FlexKV style): pink=CPU  blue=SSD/GPU  yellow=remote  green=queue
PALETTE = {
    "green":  {"bg": "#b2f2bb", "stroke": "#2f9e44"},
    "blue":   {"bg": "#a5d8ff", "stroke": "#1971c2"},
    "yellow": {"bg": "#ffec99", "stroke": "#f08c00"},
    "pink":   {"bg": "#ffc9c9", "stroke": "#e03131"},
    "purple": {"bg": "#d0bfff", "stroke": "#7048e8"},
    "gray":   {"bg": "#e9ecef", "stroke": "#495057"},
    "none":   {"bg": "transparent", "stroke": "#1e1e1e"},
}

_seed = [0]


def _s():
    _seed[0] += 1
    return _seed[0]


def rect(id, x, y, w, h, color="none", fill="solid", dash="solid", rounded=True):
    """Box. dash="dashed" for component boundaries / not-yet-materialized things.
    fill="hachure" for the hand-drawn stripe texture, "solid" for flat tint."""
    c = PALETTE[color]
    return {
        "type": "rectangle", "id": id, "x": float(x), "y": float(y),
        "width": float(w), "height": float(h),
        "strokeColor": c["stroke"], "backgroundColor": c["bg"],
        "fillStyle": fill, "strokeWidth": 2, "strokeStyle": dash,
        "roughness": 1, "opacity": 100,
        "roundness": {"type": 3} if rounded else None,
        "seed": _s(), "groupIds": [], "boundElements": [],
    }


def _text_w(s, size):
    """Estimate rendered width. The hand font is wide; CJK glyphs are full-width.
    Underestimating makes the export viewBox clip trailing characters.
    Multi-line text: width of the widest line."""
    def line_w(line):
        n_cjk = sum(1 for ch in line if ord(ch) > 0x2E7F)
        return float(size * (0.75 * (len(line) - n_cjk) + 1.1 * n_cjk))

    return max(line_w(line) for line in s.split("\n"))


def _text_h(s, size):
    """Declared height must cover every line: kroki renders declared geometry
    as-is (no re-layout), so a one-line height on a multi-line label makes the
    text block spill across the container's top border (observed 2026-07)."""
    return float(size * 1.3 * len(s.split("\n")))


def label(id, x, y, s, size=16, color="#1e1e1e", family=2):
    """Free-floating text: container titles (top-left inside the box), legends,
    annotations. family: 2=sans (default; NEVER use 1 hand-drawn — it clashes with
    code identifiers, user preference) 3=mono(code)."""
    return {
        "type": "text", "id": id, "x": float(x), "y": float(y),
        "width": _text_w(s, size), "height": _text_h(s, size),
        "text": s, "fontSize": size, "fontFamily": family,
        "strokeColor": color, "textAlign": "left", "verticalAlign": "top",
        "roughness": 1, "opacity": 100, "seed": _s(), "groupIds": [],
    }


def bind_text(container, id, s, size=16, color="#1e1e1e", family=2):
    """Centered text INSIDE a container (or inline on an arrow). Mutates the
    container's boundElements. x/y/height are pre-centered here because kroki
    renders the declared geometry as-is (excalidraw.com re-centers on load,
    kroki does not) — see _text_h."""
    w, h = _text_w(s, size), _text_h(s, size)
    t = {
        "type": "text", "id": id,
        "x": container["x"] + (container["width"] - w) / 2.0,
        "y": container["y"] + (container["height"] - h) / 2.0,
        "width": w, "height": h,
        "text": s, "fontSize": size, "fontFamily": family,
        "strokeColor": color, "textAlign": "center", "verticalAlign": "middle",
        "roughness": 1, "opacity": 100, "seed": _s(), "groupIds": [],
        "containerId": container["id"],
    }
    container["boundElements"].append({"id": id, "type": "text"})
    return t


def arrow(id, x, y, points, dash="solid", color="#1e1e1e", src=None, dst=None):
    """points = [[0,0],[dx,dy],...] relative to (x,y). dash="dashed" for
    async/feedback/cross-boundary paths. src/dst are ELEMENT dicts — binding
    keeps endpoints attached when the file is later edited in excalidraw."""
    a = {
        "type": "arrow", "id": id, "x": float(x), "y": float(y),
        "width": float(max(abs(p[0]) for p in points)),
        "height": float(max(abs(p[1]) for p in points)),
        "points": [[float(px), float(py)] for px, py in points],
        "strokeColor": color, "strokeWidth": 2, "strokeStyle": dash,
        "roughness": 1, "opacity": 100,
        "startArrowhead": None, "endArrowhead": "arrow",
        "seed": _s(), "groupIds": [], "boundElements": [],
    }
    if src is not None:
        a["startBinding"] = {"elementId": src["id"], "focus": 0, "gap": 5}
        src["boundElements"].append({"id": id, "type": "arrow"})
    if dst is not None:
        a["endBinding"] = {"elementId": dst["id"], "focus": 0, "gap": 5}
        dst["boundElements"].append({"id": id, "type": "arrow"})
    return a


def num_badge(id, cx, cy, n, r=13.0):
    """Circled step number sitting on an arrow. Returns [ellipse, text].
    (Unicode ①②③ in a plain label also renders, but the ellipse survives
    font fallback.) Pair every badge with a legend line: ① <fn>: <payload>."""
    e = {
        "type": "ellipse", "id": id, "x": float(cx - r), "y": float(cy - r),
        "width": 2 * r, "height": 2 * r,
        "strokeColor": "#1e1e1e", "backgroundColor": "#ffffff",
        "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "seed": _s(), "groupIds": [],
        "boundElements": [],
    }
    t = bind_text(e, id + "_t", str(n), size=14)
    return [e, t]


def stack(id, x, y, w, h, color="gray", n=3, offset=9.0):
    """'N replicas' idiom: n-1 offset ghost boxes (dashed) behind one solid box.
    Returns elements back-to-front; bind_text the LAST one (the solid front box).
    Annotate multiplicity next to it with label(), e.g. "× dp_size"."""
    els = []
    for i in range(n - 1, 0, -1):
        els.append(rect(f"{id}_ghost{i}", x + i * offset, y - i * offset, w, h,
                        color=color, dash="dashed"))
    els.append(rect(id, x, y, w, h, color=color))
    return els


def scene(elements):
    return {
        "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
        "elements": elements, "appState": {"viewBackgroundColor": "#ffffff"},
        "files": {},
    }


def save(path, elements, margin=50.0):
    """Writes the scene with an invisible spacer so the export gets a real
    margin (kroki pads only ~10px; edge-hugging text looks clipped)."""
    max_x = max(e["x"] + e.get("width", 0) for e in elements)
    max_y = max(e["y"] + e.get("height", 0) for e in elements)
    spacer = rect("_margin", max_x + margin, max_y + margin, 1, 1, "none")
    spacer["strokeColor"] = "transparent"
    with open(path, "w") as f:
        json.dump(scene(elements + [spacer]), f)
    # Render (needs network):
    #   curl -s -X POST -H "Content-Type: text/plain" --data-binary @FIG.excalidraw \
    #        https://kroki.io/excalidraw/svg -o FIG.svg
    # Self-check preview (macOS):
    #   qlmanage -t -s 1600 -o . FIG.svg   # then Read FIG.svg.png and LOOK at it
