#!/usr/bin/env python3
"""Tests for the Odyssey renderer."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = SCRIPT_DIR / "sample_odyssey.json"
RENDERER_PATH = SCRIPT_DIR / "render_odyssey.py"

spec = importlib.util.spec_from_file_location("render_odyssey", RENDERER_PATH)
render_odyssey = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(render_odyssey)


def load_sample() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


class OdysseyRendererTests(unittest.TestCase):
    def test_renders_sample_json_and_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            json_path, html_path = render_odyssey.render_artifacts(SAMPLE_PATH, out_dir)

            self.assertTrue(json_path.exists())
            self.assertTrue(html_path.exists())

            rendered_json = json.loads(json_path.read_text(encoding="utf-8"))
            rendered_html = html_path.read_text(encoding="utf-8")

            self.assertEqual(rendered_json["exercise"], "odyssey-planning")
            self.assertEqual([plan["id"] for plan in rendered_json["plans"]], ["life-1", "life-2", "life-3"])
            self.assertIn("localStorage", rendered_html)
            self.assertIn("Export JSON", rendered_html)
            self.assertIn("Import JSON", rendered_html)
            self.assertIn("Build public work from private curiosity", rendered_html)

    def test_rejects_missing_plans(self) -> None:
        data = load_sample()
        data["plans"] = data["plans"][:2]
        with self.assertRaisesRegex(render_odyssey.OdysseyValidationError, "exactly three"):
            render_odyssey.normalize_odyssey(data)

    def test_rejects_out_of_range_gauge(self) -> None:
        data = load_sample()
        data["plans"][0]["gauges"]["confidence"] = 101
        with self.assertRaisesRegex(render_odyssey.OdysseyValidationError, "between 0 and 100"):
            render_odyssey.normalize_odyssey(data)

    def test_rejects_missing_title(self) -> None:
        data = load_sample()
        data["plans"][1]["titleSixWords"] = ""
        with self.assertRaisesRegex(render_odyssey.OdysseyValidationError, "titleSixWords"):
            render_odyssey.normalize_odyssey(data)

    def test_rejects_malformed_timeline_year(self) -> None:
        data = load_sample()
        data["plans"][2]["timeline"][4]["year"] = "four"
        with self.assertRaisesRegex(render_odyssey.OdysseyValidationError, "integer year"):
            render_odyssey.normalize_odyssey(data)

    def test_normalization_does_not_mutate_input(self) -> None:
        data = load_sample()
        original = copy.deepcopy(data)
        render_odyssey.normalize_odyssey(data)
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
