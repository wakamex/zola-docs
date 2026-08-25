#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from navigation import validate_navigation  # noqa: E402


def convert(format_name: str, source: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="zola-docs-converter-") as temporary:
        output = Path(temporary) / "navigation.json"
        subprocess.run(
            [sys.executable, "tools/convert_navigation.py", format_name, str(source), "-o", str(output)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(output.read_text())
        validate_navigation(result)
        return result


mkdocs = convert("mkdocs", ROOT / "tests/fixtures/mkdocs.yml")
assert mkdocs["groups"][0]["title"] == "Example Manual"
assert mkdocs["groups"][0]["items"][0] == {"title": "Home", "path": ""}
guide = mkdocs["groups"][0]["items"][1]
assert guide["id"] == "guide"
assert guide["children"][1]["children"][0]["path"] == "guide/concepts/model/"
assert mkdocs["groups"][0]["items"][2]["url"] == "https://example.com/project/"

mdbook = convert("mdbook", ROOT / "tests/fixtures/SUMMARY.md")
assert [group["title"] for group in mdbook["groups"]] == ["Documentation", "Reference"]
assert mdbook["groups"][0]["items"][0] == {"title": "Introduction", "path": ""}
assert mdbook["groups"][0]["items"][1]["children"][0]["path"] == "guide/install/"
assert mdbook["groups"][1]["items"][1]["url"] == "https://example.com/"

print("MkDocs and mdBook navigation converters: 9 checks passed")
