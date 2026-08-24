#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*command: str, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def require(text: str, *needles: str) -> None:
    for needle in needles:
        if needle not in text:
            raise RuntimeError(f"Missing expected output: {needle}")


def check_demo(zola: Path) -> None:
    run(str(zola), "build")
    run(str(zola), "check")
    home = (ROOT / "public/index.html").read_text()
    guide = (ROOT / "public/guides/getting-started/index.html").read_text()
    css = (ROOT / "static/zola-docs.css").read_text()
    search = json.loads((ROOT / "public/search_index.en.json").read_text())
    require(
        home,
        'class="skip-link"',
        'role="search"',
        'aria-live="polite"',
        'aria-label="Documentation"',
        'aria-label="Documentation version"',
        'aria-current="page">Stable',
        '>Nightly</a>',
        'data-appearance-toggle',
        'class="theme-icon theme-icon-light"',
        'class="theme-icon theme-icon-dark"',
        'data-navigation-open',
        'aria-controls="mobile-navigation-dialog"',
        '<details class="sidebar-navigation-group" open>',
        'class="sidebar-chevron"',
        'id="main-content"',
        'style="max-width: 78rem"',
    )
    require(
        guide,
        '<details class="toc" open>',
        "On this page",
        'class="mermaid"',
        'type="module"',
        'class="breadcrumbs"',
        'aria-label="Page navigation"',
        'class="edit-link"',
        'class="last-updated"',
        'class="backlinks"',
        "Referenced by",
        ">Zola Docs</a>",
        'class="heading-anchor"',
        'rel="canonical"',
    )
    require(css, "prefers-color-scheme: dark", "@media (max-width: 52rem)", ":focus-visible", ".navigation-dialog", "100dvh")
    if "max-width: 76ch" in css:
        raise RuntimeError("Prose width duplicated the configurable content maximum")
    script = (ROOT / "static/zola-docs.js").read_text()
    require(
        script,
        'document.querySelector("[data-appearance-toggle]")',
        'appearance.setAttribute("aria-label", appearanceLabel + ": switch to " + action + " theme")',
        'appearance.addEventListener("click"',
        'matchMedia("(max-width: 52rem)")',
        "tableOfContents.open = !compactTableOfContents.matches",
        'document.createElement("dialog")',
        "showModal()",
        'aria-current="page"',
        "scrollIntoView",
    )
    if not all(item.get("title") for item in search):
        raise RuntimeError("Demo search index contains an empty title")
    for directory in (ROOT / "templates", ROOT / "static"):
        for path in directory.iterdir():
            if path.is_file() and "wakterm" in path.read_text().lower():
                raise RuntimeError(f"Theme runtime contains Wakterm-specific behavior: {path}")


def check_consumer_override(zola: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="zola-docs-consumer-") as temporary:
        site = Path(temporary)
        for directory in ("content", "data", "templates", "themes"):
            (site / directory).mkdir()
        os.symlink(ROOT, site / "themes/zola-docs", target_is_directory=True)
        (site / "config.toml").write_text(
            '''title = "Consumer docs"
base_url = "https://docs.example.test/manual/"
theme = "zola-docs"
compile_sass = false
build_search_index = true
generate_sitemap = false
generate_robots_txt = false

[search]
index_format = "fuse_json"
include_title = true
include_content = true
include_path = true

[extra.zola_docs]
site_name = "Consumer"
version_banner = "Preview documentation"
backlinks = true
content_max_width = "none"
'''
        )
        (site / "data/navigation.json").write_text(
            '[{"id":"consumer","title":"Consumer","items":['
            '{"title":"Page","path":"page/","children":['
            '{"title":"Child","path":"child/"}]},'
            '{"title":"Peer","path":"peer/"}]},'
            '{"id":"reference","title":"Reference","path":"reference/","items":['
            '{"title":"Hidden reference entry","path":"reference/entry/"}]}]\n'
        )
        (site / "content/_index.md").write_text(
            "+++\ntitle = \"Home\"\n+++\n\n# Home\n\n[Page](@/page.md)\n"
        )
        (site / "content/page.md").write_text(
            "+++\ntitle = \"Consumer page\"\n[extra]\npage_navigation = false\nbacklinks = false\n+++\n\n# Consumer page\n\n## Detail\n"
            .replace(
                "backlinks = false",
                'backlinks = false\nnavigation_group = "consumer"\nnavigation_branch = "page/"',
            )
        )
        (site / "templates/page.html").write_text(
            '''{% extends "zola-docs/templates/page.html" %}
{% block page_metadata %}<p data-consumer-metadata>Generated compatibility metadata</p>{% endblock page_metadata %}
{% block page_footer %}<p data-consumer-override>Consumer override</p>{% endblock page_footer %}
'''
        )
        run(str(zola), "build", cwd=site)
        page = (site / "public/page/index.html").read_text()
        require(
            page,
            "Consumer page",
            'style="max-width: none"',
            "data-consumer-metadata",
            "data-consumer-override",
            "Preview documentation",
            'href="https://docs.example.test/manual/page',
            'aria-current="page"',
            'aria-current="page">Page',
            ">Child</a>",
            ">Peer</a>",
            ">Reference</a>",
            'href="https://docs.example.test/manual/zola-docs.css?',
            "zola-docs.css",
        )
        if "version-switcher" in page:
            raise RuntimeError("Version switcher rendered when versioning was disabled")
        if 'aria-label="Page navigation"' in page:
            raise RuntimeError("Page navigation rendered when disabled for the page")
        if 'class="backlinks"' in page:
            raise RuntimeError("Backlinks rendered when disabled for the page")
        if "Hidden reference entry" in page:
            raise RuntimeError("Scoped navigation rendered an unrelated group entry")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--zola",
        type=Path,
        default=Path(os.environ.get("ZOLA_BIN", "/code/zola-ufo/target/release/zola")),
    )
    args = parser.parse_args()
    if not args.zola.is_file():
        raise SystemExit(f"Zola binary not found: {args.zola}")
    check_demo(args.zola)
    check_consumer_override(args.zola)
    run("node", "tests/search.test.js")
    print("theme demo, consumer override, responsive CSS, accessibility markup, and search: passed")


if __name__ == "__main__":
    main()
