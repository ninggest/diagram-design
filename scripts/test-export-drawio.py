#!/usr/bin/env python3
"""Regression tests for the draw.io export (shape graph, glued connectors).

Covers the packaged helper at skills/diagram-design/scripts/export_drawio.py
and the contract documented in references/export.md.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "skills/diagram-design/scripts/export_drawio.py"
DRAWIO_EXTRACT = ROOT / "skills/diagram-design/scripts/drawio_extract.py"

SIMPLE_FLOW = """<!DOCTYPE html>
<html><body><svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="40" y="60" width="120" height="48" rx="6" fill="#ffffff" stroke="#2d3142"/>
  <text x="100" y="82" text-anchor="middle" font-size="12" font-family="Geist">Step A</text>
  <rect x="240" y="60" width="120" height="48" rx="6" fill="#ffffff" stroke="#2d3142"/>
  <text x="300" y="82" text-anchor="middle" font-size="12" font-family="Geist">Step B</text>
  <path d="M160,84 H240" fill="none" stroke="#4f5d75" stroke-width="1.2" marker-end="url(#arrow)"/>
</svg></body></html>
"""

SWIMLANE = """<!DOCTYPE html>
<html><body><svg viewBox="0 0 600 300" xmlns="http://www.w3.org/2000/svg">
  <line x1="40" y1="60" x2="560" y2="60" stroke="rgba(45,49,66,0.22)"/>
  <line x1="40" y1="140" x2="560" y2="140" stroke="rgba(45,49,66,0.10)"/>
  <line x1="40" y1="220" x2="560" y2="220" stroke="rgba(45,49,66,0.22)"/>
  <text x="56" y="104" font-size="12" font-family="Geist">Lane One</text>
  <rect x="190" y="80" width="120" height="40" rx="6" fill="#ffffff" stroke="#2d3142"/>
  <text x="250" y="104" text-anchor="middle" font-size="12" font-family="Geist">In Lane</text>
</svg></body></html>
"""

CAPTION = """<!DOCTYPE html>
<html><body><svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="200" y="60" width="12" height="80" fill="#2d3142"/>
  <text x="184" y="104" text-anchor="end" font-size="12" font-family="Geist">Value</text>
</svg></body></html>
"""

RIBBON = """<!DOCTYPE html>
<html><body><svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
  <path d="M40,60 C140,60 140,140 240,140 L240,180 C140,180 140,100 40,100 Z" fill="rgba(79,93,117,0.18)"/>
</svg></body></html>
"""


def load_helper():
    spec = importlib.util.spec_from_file_location("diagram_design_export_drawio", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cells(document: str) -> list[ET.Element]:
    return [element for element in ET.fromstring(document).iter() if element.tag == "mxCell"]


def style_of(cell: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (cell.get("style") or "").split(";"):
        part = part.strip()
        if not part:
            continue
        key, _, value = part.partition("=")
        out[key.strip()] = value.strip()
    return out


class ExportDrawioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_helper()

    def export(self, source: str) -> ET.Element:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "diagram.html"
            out = Path(tmp) / "diagram.drawio"
            html.write_text(source, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.mod.main([str(html), str(out)]), 0)
            return ET.parse(out).getroot()

    def test_document_is_a_wellformed_mxfile(self) -> None:
        root = self.export(SIMPLE_FLOW)
        self.assertEqual(root.tag, "mxfile")
        self.assertIsNotNone(root.find(".//mxGraphModel"))
        self.assertIsNotNone(root.find(".//root"))

    def test_steps_become_vertices_with_their_labels(self) -> None:
        root = self.export(SIMPLE_FLOW)
        vertices = [c for c in cells(ET.tostring(root, encoding="unicode")) if c.get("vertex") == "1"]
        self.assertEqual(len(vertices), 2)
        self.assertEqual(
            sorted(c.get("value") for c in vertices), ["Step A", "Step B"]
        )
        for vertex in vertices:
            self.assertEqual(style_of(vertex).get("rounded"), "1")
            self.assertEqual(style_of(vertex).get("fillColor"), "#ffffff")

    def test_connector_is_glued_to_its_source_and_target(self) -> None:
        root = self.export(SIMPLE_FLOW)
        all_cells = cells(ET.tostring(root, encoding="unicode"))
        edges = [c for c in all_cells if c.get("edge") == "1"]
        self.assertEqual(len(edges), 1)
        edge = edges[0]
        vertices = {c.get("id"): c.get("value") for c in all_cells if c.get("vertex") == "1"}
        self.assertEqual(vertices[edge.get("source")], "Step A")
        self.assertEqual(vertices[edge.get("target")], "Step B")
        style = style_of(edge)
        self.assertEqual(style.get("edgeStyle"), "orthogonalEdgeStyle")
        self.assertEqual(style.get("endArrow"), "classic")
        self.assertEqual(style.get("exitX"), "1.0000")
        self.assertEqual(style.get("entryX"), "0.0000")

    def test_swimlane_band_becomes_a_container_holding_its_steps(self) -> None:
        root = self.export(SWIMLANE)
        all_cells = cells(ET.tostring(root, encoding="unicode"))
        containers = [c for c in all_cells if style_of(c).get("container") == "1"]
        self.assertEqual(len(containers), 1)
        lane = containers[0]
        self.assertEqual(lane.get("value"), "Lane One")
        children = [c for c in all_cells if c.get("parent") == lane.get("id")]
        self.assertEqual([c.get("value") for c in children], ["In Lane"])
        # The step's geometry is relative to the container's origin.
        geometry = children[0].find("mxGeometry")
        self.assertEqual(geometry.get("x"), "150")
        self.assertEqual(geometry.get("y"), "20")

    def test_lane_rule_is_replaced_by_the_container_border(self) -> None:
        root = self.export(SWIMLANE)
        all_cells = cells(ET.tostring(root, encoding="unicode"))
        rules = [
            c for c in all_cells
            if c.get("edge") == "1" and c.get("source") is None and c.get("target") is None
        ]
        # Three full-width rules went in; the two that bound a lane become the
        # container border, so only the unused one survives as a decoration.
        self.assertLessEqual(len(rules), 1)

    def test_caption_becomes_a_child_of_the_node_it_captions(self) -> None:
        root = self.export(CAPTION)
        all_cells = cells(ET.tostring(root, encoding="unicode"))
        bar = [c for c in all_cells if c.get("vertex") == "1" and not c.get("value")][0]
        captions = [c for c in all_cells if c.get("parent") == bar.get("id")]
        self.assertEqual(len(captions), 1)
        self.assertIn("Value", captions[0].get("value"))
        geometry = captions[0].find("mxGeometry")
        # The caption sits to the left of the bar, so its x is negative.
        self.assertTrue(int(geometry.get("x")) < 0)

    def test_filled_band_becomes_a_polygon_vertex(self) -> None:
        root = self.export(RIBBON)
        all_cells = cells(ET.tostring(root, encoding="unicode"))
        polygons = [
            c for c in all_cells if "polyCoords" in style_of(c)
        ]
        self.assertEqual(len(polygons), 1)
        style = style_of(polygons[0])
        self.assertEqual(style.get("shape"), "mxgraph.basic.polygon")
        self.assertEqual(style.get("fillColor"), "#4f5d75")
        self.assertEqual(style.get("fillOpacity"), "18")
        self.assertTrue(style.get("polyCoords", "").startswith("[["))

    def test_missing_svg_is_a_named_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "diagram.html"
            out = Path(tmp) / "diagram.drawio"
            html.write_text("<!DOCTYPE html><html><body><p>no svg</p></body></html>", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.mod.main([str(html), str(out)]), 2)
            self.assertFalse(out.exists())

    def test_exported_file_reads_back_through_the_import_extractor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "diagram.html"
            out = Path(tmp) / "diagram.drawio"
            html.write_text(SIMPLE_FLOW, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.mod.main([str(html), str(out)]), 0)
            result = subprocess.run(
                [sys.executable, str(DRAWIO_EXTRACT), str(out)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Step A", result.stdout)
            self.assertIn("Step B", result.stdout)
            self.assertIn("Step A | Step B", result.stdout)


if __name__ == "__main__":
    unittest.main()
