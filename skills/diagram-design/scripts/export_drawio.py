#!/usr/bin/env python3
"""Export a diagram HTML/SVG into an editable .drawio (mxGraph) file.

Ships inside the skill so an installed agent can produce a portable .drawio
without re-deriving the transform:

    python3 <skill-dir>/scripts/export_drawio.py my-diagram.html
    python3 <skill-dir>/scripts/export_drawio.py my-diagram.svg out.drawio

SVG carries geometry but not semantics. A ``<path>`` knows it was drawn from
A's right edge to B's bottom edge, but not that A is the *source* and B the
*target*, nor which shapes belong together. draw.io and Visio need exactly
that missing layer -- a shape graph with glued connectors -- so a plain SVG
round-trip degrades into loose shapes and dead lines.

This exporter reconstructs that layer from a contract the skill guarantees:
every connector starts on the source shape's border and ends on the target
shape's border. Matching the path's first/last point against the node
rectangles therefore recovers source, target and the attach fractions
(exitX/exitY, entryX/entryY) exactly -- which is what makes the result
editable rather than merely decorative.

Two further semantics are recovered the same way:

* Swimlane bands become draw.io containers, so a step dragged into a lane
  belongs to it and moving the lane moves its steps.
* A caption that sits beside or above a node becomes that node's child, so it
  travels with it instead of stranding when the node is dragged.

Filled bands (Sankey ribbons and the like) become polygon vertices: the
curves are flattened and carried as ``polyCoords``, which is a shape draw.io
and Visio both understand as a real object rather than a picture.

The algorithm matches ``references/export.md``. No third-party deps.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Iterator

# Border contact tolerance. The skill's connectors land exactly on a border;
# the tolerance only absorbs rounding in the authored coordinates.
CONTACT_TOL = 2.0

# How far a free-standing label may sit from a connector before it stops
# being that connector's label.
LABEL_CATCH_RADIUS = 36.0

# Points sampled per Bezier segment when flattening a filled band.
CURVE_SAMPLES = 10

FULLWIDTH_ADVANCE = 1.0   # em, per style-guide.md width budget
SANS_ADVANCE = 0.60       # em
MONO_ADVANCE = 0.62       # em

PAPER_HEX = "#f5f5f5"


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def local(tag: str) -> str:
    """Strip the SVG namespace from a tag name."""
    return tag.rsplit("}", 1)[-1]


def num(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def parse_color(value: str | None) -> tuple[str | None, int | None]:
    """Return (hex color or None, opacity 0-100 or None).

    draw.io has no rgba(); it wants a hex plus a separate fillOpacity /
    strokeOpacity percentage. Splitting the alpha out keeps the value intact
    instead of blending it against an assumed background.
    """
    if not value:
        return None, None
    raw = value.strip()
    lowered = raw.lower()
    if lowered in ("none", "transparent"):
        return "none", None
    match = re.match(
        r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)",
        raw,
    )
    if match:
        red, green, blue = (int(float(match.group(i))) for i in (1, 2, 3))
        red, green, blue = (max(0, min(255, c)) for c in (red, green, blue))
        alpha = match.group(4)
        opacity = round(float(alpha) * 100) if alpha is not None else None
        return "#%02x%02x%02x" % (red, green, blue), opacity
    if raw.startswith("#"):
        return raw.lower(), None
    return None, None


def text_advance(text: str, font_size: float, mono: bool) -> float:
    """Width of a text run, per the style guide's budget.

    Every Unicode wide/full-width character costs 1em; everything else costs
    the face's Latin advance. Per character, not per script -- a string that
    mixes CJK and Latin is not as wide as its CJK count alone.
    """
    width = 0.0
    for char in text:
        if unicodedian_width(char) in ("W", "F"):
            width += font_size * FULLWIDTH_ADVANCE
        else:
            width += font_size * (MONO_ADVANCE if mono else SANS_ADVANCE)
    return width


def unicodedian_width(char: str) -> str:
    return unicodedata.east_asian_width(char)


def is_mono(font_family: str | None) -> bool:
    return "Mono" in (font_family or "")


# --------------------------------------------------------------------------
# path parsing
# --------------------------------------------------------------------------
PATH_TOKEN_RE = re.compile(r"[MmLlHhVvCcSsQqTtZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")


def walk_path(data: str) -> Iterator[tuple[str, tuple[float, ...]]]:
    """Yield (command, arguments) for a path's commands.

    Only the commands the skill emits are honoured (absolute M/L/H/V/C/Q/Z,
    plus their relative twins for robustness).
    """
    tokens = PATH_TOKEN_RE.findall(data or "")
    current = (0.0, 0.0)
    start = (0.0, 0.0)
    command = ""
    index = 0

    def take() -> float:
        nonlocal index
        value = float(tokens[index])
        index += 1
        return value

    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command in "Zz":
                yield ("Z", ())
                current = start
                continue
            if command.lower() not in "mlhvcsqt":
                command = ""
                continue
        if not command:
            index += 1
            continue

        lower = command.lower()
        relative = command.islower()
        if lower == "m":
            x, y = take(), take()
            if relative:
                x, y = current[0] + x, current[1] + y
            current = (x, y)
            start = current
            yield ("M", (x, y))
            command = "l" if relative else "L"
        elif lower == "l":
            x, y = take(), take()
            if relative:
                x, y = current[0] + x, current[1] + y
            current = (x, y)
            yield ("L", (x, y))
        elif lower == "h":
            x = take()
            if relative:
                x = current[0] + x
            current = (x, current[1])
            yield ("L", (x, current[1]))
        elif lower == "v":
            y = take()
            if relative:
                y = current[1] + y
            current = (current[0], y)
            yield ("L", (current[0], y))
        elif lower == "c":
            x1, y1, x2, y2, x, y = (take() for _ in range(6))
            if relative:
                x1, y1 = current[0] + x1, current[1] + y1
                x2, y2 = current[0] + x2, current[1] + y2
                x, y = current[0] + x, current[1] + y
            yield ("C", (x1, y1, x2, y2, x, y))
            current = (x, y)
        elif lower == "s":
            x2, y2, x, y = (take() for _ in range(4))
            if relative:
                x2, y2 = current[0] + x2, current[1] + y2
                x, y = current[0] + x, current[1] + y
            yield ("C", (current[0], current[1], x2, y2, x, y))
            current = (x, y)
        elif lower == "q":
            x1, y1, x, y = (take() for _ in range(4))
            if relative:
                x1, y1 = current[0] + x1, current[1] + y1
                x, y = current[0] + x, current[1] + y
            yield ("Q", (x1, y1, x, y))
            current = (x, y)
        elif lower == "t":
            x, y = take(), take()
            if relative:
                x, y = current[0] + x, current[1] + y
            yield ("Q", (current[0], current[1], x, y))
            current = (x, y)
        else:
            index += 1


def path_endpoints(data: str) -> tuple[list[tuple[float, float]], bool]:
    """On-path points (command endpoints) and whether the path is closed."""
    points: list[tuple[float, float]] = []
    closed = False
    for command, args in walk_path(data):
        if command == "Z":
            closed = True
            continue
        if command == "C":
            points.append((args[4], args[5]))
        elif command == "Q":
            points.append((args[2], args[3]))
        else:
            points.append((args[0], args[1]))
    return points, closed


def flatten_path(data: str, samples: int = CURVE_SAMPLES) -> list[tuple[float, float]]:
    """Flatten a path into a closed polygon outline.

    Curves become straight chords, so the result is a polygon draw.io can
    hold as a real shape.
    """
    outline: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    for command, args in walk_path(data):
        if command == "M":
            current = (args[0], args[1])
            outline.append(current)
        elif command == "L":
            current = (args[0], args[1])
            outline.append(current)
        elif command == "C":
            x1, y1, x2, y2, x, y = args
            for step in range(1, samples + 1):
                t = step / samples
                point = cubic_at(current, (x1, y1), (x2, y2), (x, y), t)
                outline.append(point)
            current = (x, y)
        elif command == "Q":
            x1, y1, x, y = args
            for step in range(1, samples + 1):
                t = step / samples
                outline.append(quadratic_at(current, (x1, y1), (x, y), t))
            current = (x, y)
    return outline


def cubic_at(p0: tuple[float, float], p1: tuple[float, float],
             p2: tuple[float, float], p3: tuple[float, float], t: float) -> tuple[float, float]:
    u = 1.0 - t
    a = u * u * u
    b = 3 * u * u * t
    c = 3 * u * t * t
    d = t * t * t
    return (
        a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
        a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
    )


def quadratic_at(p0: tuple[float, float], p1: tuple[float, float],
                 p2: tuple[float, float], t: float) -> tuple[float, float]:
    u = 1.0 - t
    a = u * u
    b = 2 * u * t
    c = t * t
    return (
        a * p0[0] + b * p1[0] + c * p2[0],
        a * p0[1] + b * p1[1] + c * p2[1],
    )


# --------------------------------------------------------------------------
# SVG model
# --------------------------------------------------------------------------
class Node:
    """A rectangle the skill drew as a step box or a value bar."""

    __slots__ = ("x", "y", "w", "h", "rx", "fill", "stroke", "fill_opacity",
                 "stroke_opacity", "dashed", "stroke_width", "labels", "cell_id")

    def __init__(self, x: float, y: float, w: float, h: float, rx: float) -> None:
        self.x, self.y, self.w, self.h, self.rx = x, y, w, h, rx
        self.fill = ""
        self.stroke = ""
        self.fill_opacity: int | None = None
        self.stroke_opacity: int | None = None
        self.dashed = False
        self.stroke_width = 1.0
        self.labels: list[tuple[float, str, dict[str, str]]] = []
        self.cell_id = ""

    def contains(self, px: float, py: float, inset: float = 0.0) -> bool:
        return (
            self.x - inset <= px <= self.x + self.w + inset
            and self.y - inset <= py <= self.y + self.h + inset
        )

    def on_border(self, px: float, py: float, tol: float = CONTACT_TOL) -> bool:
        inside_x = self.x - tol <= px <= self.x + self.w + tol
        inside_y = self.y - tol <= py <= self.y + self.h + tol
        near_left = abs(px - self.x) <= tol
        near_right = abs(px - (self.x + self.w)) <= tol
        near_top = abs(py - self.y) <= tol
        near_bottom = abs(py - (self.y + self.h)) <= tol
        if near_left or near_right:
            return inside_y
        if near_top or near_bottom:
            return inside_x
        return False

    def fraction_x(self, px: float) -> float:
        return 0.0 if self.w <= 0 else (px - self.x) / self.w

    def fraction_y(self, py: float) -> float:
        return 0.0 if self.h <= 0 else (py - self.y) / self.h


class Connector:
    """A stroked, unfilled path or line: the skill's connectors."""

    __slots__ = ("points", "closed", "stroke", "stroke_opacity", "stroke_width",
                 "dashed", "arrow_end", "source", "target", "exit_x", "exit_y",
                 "entry_x", "entry_y", "labels", "cell_id")

    def __init__(self, points: list[tuple[float, float]], closed: bool) -> None:
        self.points = points
        self.closed = closed
        self.stroke = ""
        self.stroke_opacity: int | None = None
        self.stroke_width = 1.0
        self.dashed = False
        self.arrow_end = False
        self.source: Node | None = None
        self.target: Node | None = None
        self.exit_x = self.exit_y = 0.0
        self.entry_x = self.entry_y = 0.0
        self.labels: list[tuple[float, str, dict[str, str]]] = []
        self.cell_id = ""

    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def length(self) -> float:
        total = 0.0
        for (x1, y1), (x2, y2) in zip(self.points, self.points[1:]):
            total += math.hypot(x2 - x1, y2 - y1)
        return total

    def project(self, px: float, py: float) -> tuple[float, float]:
        """Return (fraction along the polyline, distance to it)."""
        if not self.points:
            return 0.0, math.inf
        total = self.length()
        if total <= 0 or len(self.points) < 2:
            return 0.0, math.hypot(px - self.points[0][0], py - self.points[0][1])
        best = (0.0, math.inf)
        walked = 0.0
        for (x1, y1), (x2, y2) in zip(self.points, self.points[1:]):
            seg = math.hypot(x2 - x1, y2 - y1)
            if seg <= 0:
                continue
            t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (seg * seg)
            t = max(0.0, min(1.0, t))
            cx, cy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
            distance = math.hypot(px - cx, py - cy)
            if distance < best[1]:
                best = ((walked + t * seg) / total, distance)
            walked += seg
        return best


class Band:
    """A filled closed path: a Sankey ribbon. Becomes a polygon vertex."""

    __slots__ = ("outline", "fill", "fill_opacity", "stroke", "stroke_opacity",
                 "x", "y", "w", "h", "cell_id")

    def __init__(self, outline: list[tuple[float, float]]) -> None:
        self.outline = outline
        self.fill = ""
        self.fill_opacity: int | None = None
        self.stroke = ""
        self.stroke_opacity: int | None = None
        xs = [p[0] for p in outline]
        ys = [p[1] for p in outline]
        self.x, self.y = min(xs), min(ys)
        self.w, self.h = max(xs) - min(xs), max(ys) - min(ys)
        self.cell_id = ""

    def poly_coords(self) -> str:
        width = self.w or 1.0
        height = self.h or 1.0
        parts = []
        for px, py in self.outline:
            nx = (px - self.x) / width
            ny = (py - self.y) / height
            parts.append("[%.4f,%.4f]" % (nx, ny))
        return "[" + ",".join(parts) + "]"


class Decoration:
    """A shape that carries no semantics: dividers, swatches, legend rules."""

    __slots__ = ("x", "y", "w", "h", "kind", "fill", "stroke", "fill_opacity",
                 "stroke_opacity", "dashed", "stroke_width", "points", "arrow_end")

    def __init__(self, x: float, y: float, w: float, h: float, kind: str) -> None:
        self.x, self.y, self.w, self.h, self.kind = x, y, w, h, kind
        self.fill = ""
        self.stroke = ""
        self.fill_opacity: int | None = None
        self.stroke_opacity: int | None = None
        self.dashed = False
        self.stroke_width = 1.0
        self.arrow_end = False
        self.points: tuple[float, float, float, float] = (x, y, x + w, y + h)


class Text:
    """A <text> run."""

    __slots__ = ("x", "y", "content", "size", "family", "weight", "fill", "anchor",
                 "box", "node", "connector", "consumed")

    def __init__(self, x: float, y: float, content: str, size: float,
                 family: str, weight: str, fill: str, anchor: str) -> None:
        self.x, self.y = x, y
        self.content = content
        self.size = size
        self.family = family
        self.weight = weight
        self.fill = fill
        self.anchor = anchor
        self.consumed = False
        # The budget is an estimate of the glyph advances; the box needs a little
        # slack on top of it or the renderer wraps a single-line label that
        # fits. Six pixels a side is enough for CJK at the ramp sizes.
        width = text_advance(content, size, is_mono(family)) + 12
        if anchor == "middle":
            left = x - width / 2
        elif anchor == "end":
            left = x - width
        else:
            left = x
        self.box = (left, y - size * 0.8, left + width, y + size * 0.25)
        self.node: Node | None = None
        self.connector: Connector | None = None


# --------------------------------------------------------------------------
# SVG parsing
# --------------------------------------------------------------------------
def extract_svg(html: str) -> str:
    """Pull the first top-level <svg> element out of an HTML document."""
    in_tag = re.compile(r"<svg\b", re.IGNORECASE)
    close_tag = re.compile(r"</svg\s*>", re.IGNORECASE)
    position = 0
    while True:
        start = in_tag.search(html, position)
        if not start:
            raise ValueError("no <svg> element found")
        depth = 0
        cursor = start.start()
        while cursor < len(html):
            open_match = in_tag.search(html, cursor)
            close_match = close_tag.search(html, cursor)
            if not close_match:
                raise ValueError("unterminated <svg> element")
            if open_match and open_match.start() < close_match.start():
                depth += 1
                cursor = open_match.end()
                continue
            depth -= 1
            cursor = close_match.end()
            if depth == 0:
                return html[start.start():cursor]
        raise ValueError("unterminated <svg> element")


class Lane:
    """A swimlane band: becomes a draw.io container holding its steps."""

    __slots__ = ("x", "y", "w", "h", "label", "label_text", "cell_id", "nodes")

    def __init__(self, x: float, y: float, w: float, h: float) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h
        self.label = ""
        self.label_text: Text | None = None
        self.cell_id = ""
        self.nodes: list[Node] = []


class Diagram:
    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.connectors: list[Connector] = []
        self.bands: list[Band] = []
        self.decorations: list[Decoration] = []
        self.texts: list[Text] = []
        self.lanes: list[Lane] = []
        self.page_width = 1000.0
        self.page_height = 1000.0


def parse_svg(source: str) -> Diagram:
    root = ET.fromstring(source)
    diagram = Diagram()

    view_box = root.get("viewBox", "0 0 1000 1000").split()
    try:
        origin_x, origin_y = float(view_box[0]), float(view_box[1])
        diagram.page_width = float(view_box[2])
        diagram.page_height = float(view_box[3])
    except (IndexError, ValueError):
        origin_x, origin_y = 0.0, 0.0

    def handle_rect(element: ET.Element) -> None:
        width_raw = element.get("width", "0")
        height_raw = element.get("height", "0")
        if width_raw.endswith("%") or height_raw.endswith("%"):
            return  # the page-sized background
        x = num(element.get("x")) - origin_x
        y = num(element.get("y")) - origin_y
        width = num(width_raw)
        height = num(height_raw)
        radius = num(element.get("rx"))
        fill, fill_opacity = parse_color(element.get("fill"))
        stroke, stroke_opacity = parse_color(element.get("stroke"))
        dashed = bool(element.get("stroke-dasharray"))
        stroke_width = num(element.get("stroke-width"), 1.0)
        has_stroke = bool(stroke and stroke != "none")
        has_fill = bool(fill and fill != "none")

        # A step box: rounded, or a solid value bar (a Sankey node).
        is_box = (radius >= 4 and width >= 40 and height >= 20) or (
            not has_stroke and has_fill and width >= 8 and height >= 20
            and fill != PAPER_HEX
        )
        if is_box:
            node = Node(x, y, width, height, radius)
            node.fill = fill or ""
            node.stroke = stroke or ""
            node.fill_opacity = fill_opacity
            node.stroke_opacity = stroke_opacity
            node.dashed = dashed
            node.stroke_width = stroke_width
            diagram.nodes.append(node)
            return
        if has_stroke:
            deco = Decoration(x, y, width, height, "rect")
            deco.fill = fill or ""
            deco.stroke = stroke
            deco.fill_opacity = fill_opacity
            deco.stroke_opacity = stroke_opacity
            deco.dashed = dashed
            deco.stroke_width = stroke_width
            diagram.decorations.append(deco)
        # A fill-only rect in the paper colour is a label mask: skip it.

    def handle_line(element: ET.Element) -> None:
        x1 = num(element.get("x1")) - origin_x
        y1 = num(element.get("y1")) - origin_y
        x2 = num(element.get("x2")) - origin_x
        y2 = num(element.get("y2")) - origin_y
        stroke, stroke_opacity = parse_color(element.get("stroke"))
        if not stroke or stroke == "none":
            return
        marker = element.get("marker-end") or ""
        if "arrow" in marker:
            # A <line> carrying an arrowhead is a connector, not a divider.
            connector = Connector([(x1, y1), (x2, y2)], False)
            connector.stroke = stroke
            connector.stroke_opacity = stroke_opacity
            connector.stroke_width = num(element.get("stroke-width"), 1.0)
            connector.dashed = bool(element.get("stroke-dasharray"))
            connector.arrow_end = True
            diagram.connectors.append(connector)
            return
        deco = Decoration(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1), "line")
        deco.stroke = stroke
        deco.stroke_opacity = stroke_opacity
        deco.dashed = bool(element.get("stroke-dasharray"))
        deco.stroke_width = num(element.get("stroke-width"), 1.0)
        deco.points = (x1, y1, x2, y2)
        diagram.decorations.append(deco)

    def handle_path(element: ET.Element) -> None:
        data = element.get("d", "")
        if not data:
            return
        points, closed = path_endpoints(data)
        if not points:
            return
        fill, fill_opacity = parse_color(element.get("fill"))
        stroke, stroke_opacity = parse_color(element.get("stroke"))
        is_connector = (not fill or fill == "none") and stroke and stroke != "none"
        if is_connector:
            connector = Connector(points, closed)
            connector.stroke = stroke
            connector.stroke_opacity = stroke_opacity
            connector.stroke_width = num(element.get("stroke-width"), 1.0)
            connector.dashed = bool(element.get("stroke-dasharray"))
            connector.arrow_end = "arrow" in (element.get("marker-end") or "")
            diagram.connectors.append(connector)
            return
        if fill and fill != "none":
            outline = flatten_path(data)
            if len(outline) >= 3:
                band = Band(outline)
                band.fill = fill
                band.fill_opacity = fill_opacity
                band.stroke = stroke or ""
                band.stroke_opacity = stroke_opacity
                diagram.bands.append(band)

    def handle_text(element: ET.Element) -> None:
        content = "".join(element.itertext()).strip()
        if not content:
            return
        x = num(element.get("x")) - origin_x
        y = num(element.get("y")) - origin_y
        size = num(element.get("font-size"), 12.0)
        family = element.get("font-family", "") or ""
        weight = element.get("font-weight", "") or ""
        fill, _ = parse_color(element.get("fill"))
        anchor = element.get("text-anchor", "start")
        diagram.texts.append(
            Text(x, y, content, size, family, weight, fill or "", anchor)
        )

    def walk(element: ET.Element) -> None:
        for child in element:
            tag = local(child.tag)
            if tag == "defs":
                continue
            if tag == "rect":
                handle_rect(child)
            elif tag == "line":
                handle_line(child)
            elif tag == "path":
                handle_path(child)
            elif tag == "text":
                handle_text(child)
            walk(child)

    walk(root)
    return diagram


def bind_labels(diagram: Diagram) -> None:
    """Attach text runs to the node they label, or to the connector they annotate."""
    for text in diagram.texts:
        center_x = (text.box[0] + text.box[2]) / 2
        center_y = (text.box[1] + text.box[3]) / 2
        best_node: Node | None = None
        best_area = math.inf
        for node in diagram.nodes:
            if node.contains(center_x, center_y):
                area = node.w * node.h
                if area < best_area:
                    best_area = area
                    best_node = node
        if best_node is not None:
            text.node = best_node
            best_node.labels.append((text.size, text.content, {
                "fill": text.fill,
                "family": text.family,
                "weight": text.weight,
            }))
            continue

        best_connector: Connector | None = None
        best_distance = math.inf
        for connector in diagram.connectors:
            if len(connector.points) < 2:
                continue
            x0, y0, x1, y1 = connector.bbox()
            if (
                x0 - LABEL_CATCH_RADIUS <= center_x <= x1 + LABEL_CATCH_RADIUS
                and y0 - LABEL_CATCH_RADIUS <= center_y <= y1 + LABEL_CATCH_RADIUS
            ):
                _, distance = connector.project(center_x, center_y)
                if distance < best_distance:
                    best_distance = distance
                    best_connector = connector
        if best_connector is not None and best_distance <= LABEL_CATCH_RADIUS:
            text.connector = best_connector
            best_connector.labels.append((text.size, text.content, {
                "fill": text.fill,
                "family": text.family,
                "weight": text.weight,
            }))


def demote_legend_arrows(diagram: Diagram) -> int:
    """Turn the legend's sample arrows back into decoration.

    A legend key is drawn as an arrow, so structurally it is a connector. But
    it touches no shape, and its length is a fraction of the shortest real
    connector (the gap between two boxes). Treating it as a legend key keeps
    the legend's own captions free-standing text instead of edge labels
    hanging off a key that means nothing.
    """
    demoted = 0
    for connector in list(diagram.connectors):
        if len(connector.points) < 2 or connector.length() >= 36:
            continue
        start, end = connector.points[0], connector.points[-1]
        if any(node.on_border(start[0], start[1]) or node.on_border(end[0], end[1])
               for node in diagram.nodes):
            continue
        x0, y0, x1, y1 = connector.bbox()
        deco = Decoration(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), "line")
        deco.stroke = connector.stroke
        deco.stroke_opacity = connector.stroke_opacity
        deco.dashed = connector.dashed
        deco.stroke_width = connector.stroke_width
        deco.arrow_end = connector.arrow_end
        deco.points = (connector.points[0][0], connector.points[0][1],
                       connector.points[-1][0], connector.points[-1][1])
        diagram.decorations.append(deco)
        diagram.connectors.remove(connector)
        demoted += 1
    return demoted


def detect_lanes(diagram: Diagram) -> list[Lane]:
    """Find the swimlane bands in a swimlane diagram.

    The skill draws lanes as full-width horizontal hairlines with the role
    name in the left margin. A band is the span between two such lines, and
    a band only counts as a lane when it holds at least one step -- that is
    what keeps the legend rule (also full width) from becoming an empty lane.
    """
    rules = [
        deco for deco in diagram.decorations
        if deco.kind == "line"
        and abs(deco.points[3] - deco.points[1]) < 2
        and abs(deco.points[2] - deco.points[0]) >= 0.6 * diagram.page_width
    ]
    rules.sort(key=lambda deco: deco.points[1])
    lanes: list[Lane] = []
    used: list[Decoration] = []
    for upper, lower in zip(rules, rules[1:]):
        y0, y1 = upper.points[1], lower.points[1]
        if y1 - y0 < 40:
            continue
        x0 = min(upper.points[0], lower.points[0])
        x1 = max(upper.points[2], lower.points[2])
        lane = Lane(x0, y0, x1 - x0, y1 - y0)
        for node in diagram.nodes:
            if y0 <= node.y + node.h / 2 <= y1:
                lane.nodes.append(node)
        if lane.nodes:
            lanes.append(lane)
            used.extend((upper, lower))
    # The container border replaces the rule the skill drew as a hairline.
    if lanes:
        diagram.decorations = [
            deco for deco in diagram.decorations
            if not any(deco is rule for rule in used)
        ]
    return lanes


def assign_lane_labels(diagram: Diagram, lanes: list[Lane]) -> set[int]:
    """Give each lane its role name; return the ids of the texts consumed."""
    consumed: set[int] = set()
    for lane in lanes:
        leftmost = min(node.x for node in lane.nodes)
        for text in diagram.texts:
            if id(text) in consumed or text.node is not None or text.connector is not None:
                continue
            center_y = (text.box[1] + text.box[3]) / 2
            if not lane.y <= center_y <= lane.y + lane.h:
                continue
            if text.box[2] > leftmost:
                continue
            lane.label_text = text
            lane.label = text.content
            text.consumed = True
            consumed.add(id(text))
            break
    return consumed


LABEL_BIND_RADIUS = 40.0


def bind_captions(diagram: Diagram, consumed: set[int]) -> dict[int, list[Text]]:
    """Bind a free-standing caption to the node it captions.

    Two shapes qualify: a caption directly above or below a node -- the skill
    puts a value label in the gutter above its bar -- and a caption beside a
    node. When a caption sits in a gutter between two nodes the lower one
    wins, because that is the skill's convention for gutter labels.
    """
    grouped: dict[int, list[Text]] = {}
    for text in diagram.texts:
        if id(text) in consumed or text.node is not None or text.connector is not None:
            continue
        above: tuple[float, Node] | None = None
        below: tuple[float, Node] | None = None
        side: tuple[float, Node] | None = None
        for node in diagram.nodes:
            dx = max(0.0, node.x - text.box[2], text.box[0] - (node.x + node.w))
            dy = max(0.0, node.y - text.box[3], text.box[1] - (node.y + node.h))
            if dx == 0.0 and dy == 0.0:
                continue
            if dx == 0.0 and dy <= LABEL_BIND_RADIUS:
                if text.box[3] <= node.y:
                    if below is None or dy < below[0]:
                        below = (dy, node)
                elif text.box[1] >= node.y + node.h:
                    if above is None or dy < above[0]:
                        above = (dy, node)
                else:
                    continue
            elif dx == 0.0:
                continue
            else:
                distance = max(dx, dy)
                if distance <= LABEL_BIND_RADIUS and (side is None or distance < side[0]):
                    side = (distance, node)
        chosen: Node | None = None
        if below is not None:
            chosen = below[1]
        elif above is not None:
            chosen = above[1]
        elif side is not None:
            chosen = side[1]
        if chosen is not None:
            text.consumed = True
            grouped.setdefault(id(chosen), []).append(text)
    return grouped


def assign_ids(diagram: Diagram) -> int:
    """Give every cell a stable id; returns the next free id."""
    counter = 2
    for group in (diagram.lanes, diagram.nodes, diagram.connectors, diagram.bands):
        for cell in group:
            cell.cell_id = str(counter)
            counter += 1
    return counter


def resolve_endpoints(diagram: Diagram) -> list[str]:
    """Match each connector's endpoints to the node borders they touch."""
    warnings: list[str] = []
    for index, connector in enumerate(diagram.connectors):
        if connector.closed or len(connector.points) < 2:
            continue
        start = connector.points[0]
        end = connector.points[-1]
        for node in diagram.nodes:
            if node.on_border(start[0], start[1]):
                connector.source = node
                connector.exit_x = node.fraction_x(start[0])
                connector.exit_y = node.fraction_y(start[1])
                break
        for node in diagram.nodes:
            if node.on_border(end[0], end[1]):
                connector.target = node
                connector.entry_x = node.fraction_x(end[0])
                connector.entry_y = node.fraction_y(end[1])
                break
        if connector.source is None or connector.target is None:
            warnings.append(
                "connector %d has no source/target pair (source=%s, target=%s); "
                "exported as a floating edge"
                % (
                    index + 1,
                    connector.source is not None,
                    connector.target is not None,
                )
            )
    return warnings


# --------------------------------------------------------------------------
# mxGraph writing
# --------------------------------------------------------------------------
def style_of(parts: Iterable[tuple[str, str]]) -> str:
    return ";".join("%s=%s" % (key, value) for key, value in parts if value != "")


def lane_style(lane: Lane) -> str:
    """A swimlane band becomes a container: the role name is its own label.

    The name sits in the left margin the way the skill draws it, so the
    container doubles as the actor column -- its left border is the divider
    the skill draws as a vertical hairline.
    """
    parts = [
        ("container", "1"),
        ("collapsible", "0"),
        ("fillColor", "none"),
        ("strokeColor", "#2d3142"),
        ("strokeWidth", "1"),
        ("strokeOpacity", "10"),
        ("html", "1"),
        ("align", "left"),
        ("verticalAlign", "middle"),
        ("spacingLeft", "16"),
        ("fontSize", "12"),
        ("fontColor", "#4f5d75"),
    ]
    return style_of(parts)


def merged_caption(texts: list[Text]) -> tuple[str, tuple[float, float, float, float]]:
    """Combine the caption runs of one node into a single child label."""
    ordered = sorted(texts, key=lambda item: (item.box[1], -item.size))
    pieces = []
    for text in ordered:
        if text.weight in ("600", "700", "bold"):
            pieces.append("<b>%s</b>" % text.content)
        else:
            family = "font-family:monospace;" if is_mono(text.family) else ""
            color = text.fill or "#4f5d75"
            pieces.append(
                '<font style="font-size:%dpx;%scolor:%s">%s</font>'
                % (round(text.size), family, color, text.content)
            )
    label = "<br>".join(pieces)
    left = min(text.box[0] for text in texts)
    top = min(text.box[1] for text in texts)
    right = max(text.box[2] for text in texts)
    bottom = max(text.box[3] for text in texts)
    return label, (left, top, right, bottom)


def node_style(node: Node) -> str:
    arc = 0
    if node.rx > 0:
        smaller = min(node.w, node.h)
        if smaller > 0:
            arc = max(1, min(100, round(node.rx / smaller * 100)))
    parts = [
        ("rounded", "1" if node.rx > 0 else "0"),
        ("arcSize", str(arc)),
        ("whiteSpace", "wrap"),
        ("html", "1"),
        ("fillColor", node.fill if node.fill and node.fill != "none" else "none"),
        ("strokeColor", node.stroke if node.stroke and node.stroke != "none" else "none"),
        ("strokeWidth", str(node.stroke_width)),
        ("verticalAlign", "middle"),
        ("align", "center"),
        ("spacing", "4"),
        ("fontSize", "12"),
        ("fontColor", "#2d3142"),
    ]
    if node.fill_opacity is not None and node.fill_opacity < 100:
        parts.append(("fillOpacity", str(node.fill_opacity)))
    if node.stroke_opacity is not None and node.stroke_opacity < 100:
        parts.append(("strokeOpacity", str(node.stroke_opacity)))
    if node.dashed:
        parts.append(("dashed", "1"))
    return style_of(parts)


def node_label(node: Node) -> str:
    if not node.labels:
        return ""
    ordered = sorted(node.labels, key=lambda item: (-item[0], item[1]))
    _, name, name_meta = ordered[0]
    pieces = []
    if name_meta.get("weight") in ("600", "700", "bold"):
        pieces.append("<b>%s</b>" % name)
    else:
        pieces.append(name)
    for size, content, meta in ordered[1:]:
        color = meta.get("fill") or "#4f5d75"
        family = "font-family:monospace;" if is_mono(meta.get("family")) else ""
        pieces.append(
            '<font style="font-size:%dpx;%scolor:%s">%s</font>'
            % (round(size), family, color, content)
        )
    return "<br>".join(pieces)


def connector_style(connector: Connector) -> str:
    parts = [
        ("edgeStyle", "orthogonalEdgeStyle"),
        ("rounded", "1"),
        ("html", "1"),
        ("strokeColor", connector.stroke),
        ("strokeWidth", str(connector.stroke_width)),
        ("endArrow", "classic" if connector.arrow_end else "none"),
        ("endFill", "1"),
        ("endSize", "6"),
        ("jettySize", "auto"),
    ]
    if connector.stroke_opacity is not None and connector.stroke_opacity < 100:
        parts.append(("strokeOpacity", str(connector.stroke_opacity)))
    if connector.dashed:
        parts.append(("dashed", "1"))
        parts.append(("dashPattern", "4 3"))
    if connector.source is not None:
        parts.extend([
            ("exitX", f"{connector.exit_x:.4f}"),
            ("exitY", f"{connector.exit_y:.4f}"),
            ("exitDx", "0"),
            ("exitDy", "0"),
        ])
    if connector.target is not None:
        parts.extend([
            ("entryX", f"{connector.entry_x:.4f}"),
            ("entryY", f"{connector.entry_y:.4f}"),
            ("entryDx", "0"),
            ("entryDy", "0"),
        ])
    return style_of(parts)


def text_style(text: Text) -> str:
    align = {"start": "left", "middle": "center", "end": "right"}.get(text.anchor, "left")
    parts = [
        ("text", "1"),
        ("html", "1"),
        ("strokeColor", "none"),
        ("fillColor", "none"),
        ("align", align),
        ("verticalAlign", "middle"),
        ("whiteSpace", "wrap"),
        ("rounded", "0"),
        ("spacing", "0"),
        ("fontSize", str(round(text.size))),
        ("fontColor", text.fill or "#2d3142"),
    ]
    if is_mono(text.family):
        parts.append(("fontFamily", "monospace"))
    if text.weight in ("600", "700", "bold"):
        parts.append(("fontStyle", "1"))
    return style_of(parts)


def band_style(band: Band) -> str:
    parts = [
        ("shape", "mxgraph.basic.polygon"),
        ("polyCoords", band.poly_coords()),
        ("polyline", "0"),
        ("fillStyle", "solid"),
        ("fillColor", band.fill if band.fill and band.fill != "none" else "none"),
        ("strokeColor", band.stroke if band.stroke and band.stroke != "none" else "none"),
        ("strokeWidth", "1"),
        ("html", "1"),
    ]
    if band.fill_opacity is not None and band.fill_opacity < 100:
        parts.append(("fillOpacity", str(band.fill_opacity)))
    return style_of(parts)


def escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_mxfile(diagram: Diagram, captions: dict[int, list[Text]]) -> str:
    counter = {"n": assign_ids(diagram)}

    def next_id() -> str:
        value = str(counter["n"])
        counter["n"] += 1
        return value

    lane_of_node: dict[int, Lane] = {}
    for lane in diagram.lanes:
        for node in lane.nodes:
            lane_of_node[id(node)] = lane

    lines: list[str] = []
    lines.append('<mxfile host="app.diagrams.net" agent="diagram-design/export_drawio" type="device">')
    lines.append('  <diagram id="diagram-design-page" name="Page-1">')
    lines.append(
        '    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" '
        'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        'pageWidth="%d" pageHeight="%d" math="0" shadow="0">'
        % (round(diagram.page_width), round(diagram.page_height))
    )
    lines.append('      <root>')
    lines.append('        <mxCell id="0" />')
    lines.append('        <mxCell id="1" parent="0" />')

    # Lanes first: they are the containers the steps live in.
    for lane in diagram.lanes:
        value = ' value="%s"' % escape_attr(lane.label) if lane.label else ""
        lines.append(
            '        <mxCell id="%s"%s style="%s" vertex="1" parent="1">'
            % (lane.cell_id, value, escape_attr(lane_style(lane)))
        )
        lines.append(
            '          <mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry" />'
            % (round(lane.x), round(lane.y), max(1, round(lane.w)), max(1, round(lane.h)))
        )
        lines.append('        </mxCell>')

    # Bands first, so they sit behind the node bars.
    for band in diagram.bands:
        lines.append(
            '        <mxCell id="%s" style="%s" vertex="1" parent="1">'
            % (band.cell_id, escape_attr(band_style(band)))
        )
        lines.append(
            '          <mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry" />'
            % (round(band.x), round(band.y), max(1, round(band.w)), max(1, round(band.h)))
        )
        lines.append('        </mxCell>')

    for node in diagram.nodes:
        label = node_label(node)
        value = ' value="%s"' % escape_attr(label) if label else ""
        lane = lane_of_node.get(id(node))
        parent = lane.cell_id if lane is not None else "1"
        # A child's coordinates are relative to its parent's origin.
        origin_x = lane.x if lane is not None else 0.0
        origin_y = lane.y if lane is not None else 0.0
        lines.append(
            '        <mxCell id="%s"%s style="%s" vertex="1" parent="%s">'
            % (node.cell_id, value, escape_attr(node_style(node)), parent)
        )
        lines.append(
            '          <mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry" />'
            % (
                round(node.x - origin_x),
                round(node.y - origin_y),
                max(1, round(node.w)),
                max(1, round(node.h)),
            )
        )
        lines.append('        </mxCell>')

        # A caption bound to this node becomes its child, so it travels with it.
        bound = captions.get(id(node))
        if bound:
            caption_id = next_id()
            caption_label, caption_box = merged_caption(bound)
            lines.append(
                '        <mxCell id="%s" value="%s" style="%s" vertex="1" '
                'connectable="0" parent="%s">'
                % (caption_id, escape_attr(caption_label), escape_attr(text_style(bound[0])), node.cell_id)
            )
            lines.append(
                '          <mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry" />'
                % (
                    round(caption_box[0] - node.x),
                    round(caption_box[1] - node.y),
                    max(1, round(caption_box[2] - caption_box[0])),
                    max(1, round(caption_box[3] - caption_box[1])),
                )
            )
            lines.append('        </mxCell>')

    for connector in diagram.connectors:
        attributes = ['id="%s"' % connector.cell_id]
        attributes.append('style="%s"' % escape_attr(connector_style(connector)))
        attributes.append('edge="1"')
        attributes.append('parent="1"')
        if connector.source is not None:
            attributes.append('source="%s"' % connector.source.cell_id)
        if connector.target is not None:
            attributes.append('target="%s"' % connector.target.cell_id)
        lines.append("        <mxCell %s>" % " ".join(attributes))
        if connector.source is None and connector.target is None:
            x0, y0, x1, y1 = connector.bbox()
            lines.append('          <mxGeometry relative="1" as="geometry">')
            lines.append('            <mxPoint x="%s" y="%s" as="sourcePoint" />' % (round(x0), round(y0)))
            lines.append('            <mxPoint x="%s" y="%s" as="targetPoint" />' % (round(x1), round(y1)))
            lines.append('          </mxGeometry>')
        else:
            lines.append('          <mxGeometry relative="1" as="geometry" />')
        lines.append('        </mxCell>')

        for size, content, meta in connector.labels:
            label_id = next_id()
            label_style = style_of([
                ("edgeLabel", "1"),
                ("html", "1"),
                ("align", "center"),
                ("verticalAlign", "middle"),
                ("labelBackgroundColor", "#f5f5f5"),
                ("fontSize", str(round(size))),
                ("fontColor", meta.get("fill") or "#4f5d75"),
            ])
            center_x = (connector.bbox()[0] + connector.bbox()[2]) / 2
            center_y = (connector.bbox()[1] + connector.bbox()[3]) / 2
            fraction, _ = connector.project(center_x, center_y)
            lines.append(
                '        <mxCell id="%s" value="%s" style="%s" vertex="1" '
                'connectable="0" parent="%s">'
                % (label_id, escape_attr(content), escape_attr(label_style), connector.cell_id)
            )
            lines.append(
                '          <mxGeometry x="%.4f" y="0" relative="1" as="geometry">'
                % max(0.0, min(1.0, fraction))
            )
            lines.append('            <mxPoint as="offset" />')
            lines.append('          </mxGeometry>')
            lines.append('        </mxCell>')

    for deco in diagram.decorations:
        if deco.kind == "line":
            deco_id = next_id()
            parts = [
                ("endArrow", "classic" if deco.arrow_end else "none"),
                ("endFill", "1"),
                ("endSize", "6"),
                ("html", "1"),
                ("strokeColor", deco.stroke),
                ("strokeWidth", str(deco.stroke_width)),
            ]
            if deco.stroke_opacity is not None and deco.stroke_opacity < 100:
                parts.append(("strokeOpacity", str(deco.stroke_opacity)))
            if deco.dashed:
                parts.append(("dashed", "1"))
            lines.append(
                '        <mxCell id="%s" style="%s" edge="1" parent="1">'
                % (deco_id, escape_attr(style_of(parts)))
            )
            lines.append('          <mxGeometry relative="1" as="geometry">')
            lines.append('            <mxPoint x="%s" y="%s" as="sourcePoint" />'
                         % (round(deco.points[0]), round(deco.points[1])))
            lines.append('            <mxPoint x="%s" y="%s" as="targetPoint" />'
                         % (round(deco.points[2]), round(deco.points[3])))
            lines.append('          </mxGeometry>')
            lines.append('        </mxCell>')
        elif deco.kind == "rect" and deco.w > 0 and deco.h > 0:
            deco_id = next_id()
            parts = [
                ("rounded", "0"),
                ("html", "1"),
                ("fillColor", deco.fill if deco.fill and deco.fill != "none" else "none"),
                ("strokeColor", deco.stroke if deco.stroke and deco.stroke != "none" else "none"),
                ("strokeWidth", str(deco.stroke_width)),
            ]
            if deco.fill_opacity is not None and deco.fill_opacity < 100:
                parts.append(("fillOpacity", str(deco.fill_opacity)))
            if deco.stroke_opacity is not None and deco.stroke_opacity < 100:
                parts.append(("strokeOpacity", str(deco.stroke_opacity)))
            lines.append(
                '        <mxCell id="%s" style="%s" vertex="1" parent="1">'
                % (deco_id, escape_attr(style_of(parts)))
            )
            lines.append(
                '          <mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry" />'
                % (round(deco.x), round(deco.y), round(deco.w), round(deco.h))
            )
            lines.append('        </mxCell>')

    for text in diagram.texts:
        if text.node is not None or text.connector is not None or text.consumed:
            continue
        text_id = next_id()
        lines.append(
            '        <mxCell id="%s" value="%s" style="%s" vertex="1" parent="1">'
            % (text_id, escape_attr(text.content), escape_attr(text_style(text)))
        )
        lines.append(
            '          <mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry" />'
            % (
                round(text.box[0]),
                round(text.box[1]),
                max(1, round(text.box[2] - text.box[0])),
                max(1, round(text.box[3] - text.box[1])),
            )
        )
        lines.append('        </mxCell>')

    lines.append('      </root>')
    lines.append('    </mxGraphModel>')
    lines.append('  </diagram>')
    lines.append('</mxfile>')
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export a diagram-design HTML/SVG into an editable .drawio file."
    )
    parser.add_argument("source", help="diagram .html or .svg")
    parser.add_argument("output", nargs="?", help="target .drawio path")
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    output_path = Path(args.output) if args.output else source_path.with_suffix(".drawio")

    try:
        raw = source_path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"cannot read {source_path}: {error}", file=sys.stderr)
        return 2

    try:
        svg_source = raw if source_path.suffix.lower() == ".svg" else extract_svg(raw)
    except ValueError as error:
        print(f"{source_path}: {error}", file=sys.stderr)
        return 2

    try:
        diagram = parse_svg(svg_source)
    except ET.ParseError as error:
        print(f"{source_path}: malformed SVG: {error}", file=sys.stderr)
        return 2

    demoted = demote_legend_arrows(diagram)
    bind_labels(diagram)
    warnings = resolve_endpoints(diagram)

    diagram.lanes = detect_lanes(diagram)
    assign_lane_labels(diagram, diagram.lanes)
    captions = bind_captions(diagram, set())

    document = build_mxfile(diagram, captions)
    try:
        output_path.write_text(document, encoding="utf-8")
    except OSError as error:
        print(f"cannot write {output_path}: {error}", file=sys.stderr)
        return 2

    glued = sum(1 for c in diagram.connectors if c.source is not None and c.target is not None)
    edge_labels = sum(len(c.labels) for c in diagram.connectors)
    loose = [
        text for text in diagram.texts
        if text.node is None and text.connector is None and not text.consumed
    ]
    bound = sum(len(group) for group in captions.values())
    print(f"wrote {output_path}")
    print(
        "  %d nodes · %d connectors (%d glued to shapes) · %d edge labels · "
        "%d bands · %d decorations · %d free labels · %d bound captions"
        % (
            len(diagram.nodes),
            len(diagram.connectors),
            glued,
            edge_labels,
            len(diagram.bands),
            len(diagram.decorations),
            len(loose),
            bound,
        )
    )
    if diagram.lanes:
        print("  lanes: %d containers (%s)" % (
            len(diagram.lanes),
            ", ".join(lane.label for lane in diagram.lanes),
        ))
    if demoted:
        print("  note: %d legend sample arrow(s) kept as decoration" % demoted)
    for warning in warnings:
        print(f"  warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
