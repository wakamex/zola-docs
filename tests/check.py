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
    run("python", "tools/validate_navigation.py", "data/navigation.json")
    run(str(zola), "build")
    run(str(zola), "check")
    home = (ROOT / "public/index.html").read_text()
    guide = (ROOT / "public/guides/getting-started/index.html").read_text()
    not_found = (ROOT / "public/404.html").read_text()
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
        'href="https://example.com/nightly/"',
        'data-appearance-toggle',
        'class="theme-icon theme-icon-light"',
        'class="theme-icon theme-icon-dark"',
        'data-navigation-open',
        'aria-controls="mobile-navigation-dialog"',
        'class="sidebar-chevron is-expanded"',
        'class="sidebar-child-count"',
        'class="sidebar-child-count">1<span class="visually-hidden"> sub-pages</span>',
        "data-copy-code",
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
        ">Installation</a>",
        'aria-label="Page navigation"',
        'class="edit-link"',
        'class="last-updated"',
        'class="backlinks"',
        "Referenced by",
        ">Zola Docs</a>",
        'class="heading-anchor"',
        'rel="canonical"',
        'href="https://example.com/nightly/guides/getting-started/"',
    )
    require(not_found, "zola-docs-not-found-start", "zola-docs-not-found-end")
    require(
        css,
        "prefers-color-scheme: dark",
        "@media (max-width: 52rem)",
        "@media print",
        ":focus-visible",
        ".navigation-dialog",
        "100dvh",
        "max-width: none !important",
    )
    if "max-width: 76ch" in css:
        raise RuntimeError("Prose width duplicated the configurable content maximum")
    if 'class="sidebar-navigation-group"' in home:
        raise RuntimeError("Sidebar navigation retained click-to-toggle groups")
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
        'document.body.hasAttribute("data-copy-code")',
    )
    if "mobile-navigation-group" in script:
        raise RuntimeError("Mobile navigation restored client-side group toggles")
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
            json.dumps(
                [
                    {
                        "id": "consumer",
                        "title": "Consumer",
                        "items": [
                            {
                                "title": "Page",
                                "path": "page/",
                                "children": [
                                    {
                                        "title": "Child",
                                        "path": "page/child/",
                                        "children": [
                                            {
                                                "title": "Deep",
                                                "path": "page/child/deep/",
                                                "children": [
                                                    {
                                                        "title": "Leaf",
                                                        "path": "page/child/deep/leaf/",
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            },
                            {"title": "Peer", "path": "peer/"},
                        ],
                    },
                    {
                        "id": "reference",
                        "title": "Reference",
                        "url": "https://reference.example.test/",
                        "items": [
                            {"title": "Hidden reference entry", "path": "reference/entry/"}
                        ],
                    },
                ]
            )
            + "\n"
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
        (site / "content/deep.md").write_text(
            "+++\ntitle = \"Deep consumer page\"\npath = \"page/child/deep/leaf\"\n"
            "[extra]\nnavigation_group = \"consumer\"\nnavigation_branch = \"page/\"\n"
            "+++\n\n# Deep consumer page\n"
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
            'class="site-name" href="https://docs.example.test/manual"',
            "data-consumer-metadata",
            "data-consumer-override",
            "Preview documentation",
            'href="https://docs.example.test/manual/page',
            'aria-current="page"',
            'aria-current="page"><svg class="sidebar-chevron is-expanded"',
            'Child<span class="sidebar-child-count">',
            ">Peer</a>",
            '>Reference<span class="sidebar-child-count">',
            'href="https://reference.example.test/"',
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
        deep = (site / "public/page/child/deep/leaf/index.html").read_text()
        require(
            deep,
            "Deep consumer page",
            "Child</a>",
            "Deep</a>",
            'aria-current="page"',
            ">Leaf</a>",
        )


def check_disabled_features(zola: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="zola-docs-disabled-") as temporary:
        site = Path(temporary)
        for directory in ("content", "data", "themes"):
            (site / directory).mkdir()
        os.symlink(ROOT, site / "themes/zola-docs", target_is_directory=True)
        (site / "config.toml").write_text(
            '''title = "Minimal docs"
base_url = "https://docs.example.test/minimal/"
theme = "zola-docs"
compile_sass = false
build_search_index = false
generate_sitemap = false
generate_robots_txt = false

[extra.zola_docs]
site_name = "Minimal"
navigation_path = "data/navigation.toml"
search_enabled = false
copy_code = false
page_navigation = false
breadcrumbs = false
toc = false
backlinks = false
edit_url = "https://example.test/edit"
last_updated = false
appearance_selector = false
metadata = false
mermaid = false
versions_enabled = false
'''
        )
        (site / "data/navigation.toml").write_text(
            '[[groups]]\nid = "minimal"\ntitle = "Minimal"\n\n'
            '[[groups.items]]\ntitle = "Page"\npath = "page/"\n'
        )
        (site / "content/_index.md").write_text("+++\ntitle = \"Home\"\n+++\n\n# Home\n")
        (site / "content/page.md").write_text(
            "+++\ntitle = \"Minimal page\"\nupdated = 2026-08-24\n"
            "[extra]\nedit_link = false\n"
            "breadcrumbs = [{ title = \"Home\", path = \"\" }]\n"
            "previous = { title = \"Home\", path = \"\" }\n"
            "next = { title = \"Home\", path = \"\" }\n"
            "+++\n\n# Minimal page\n\n## Detail\n\n```sh\necho hello\n```\n\n"
            "<pre class=\"mermaid\">graph TD; A--&gt;B</pre>\n"
        )
        run(str(zola), "build", cwd=site)
        run(str(zola), "check", cwd=site)
        page = (site / "public/page/index.html").read_text()
        require(page, "Minimal page", "echo hello", "zola-docs.js")
        forbidden = (
            "data-copy-code",
            "data-appearance-toggle",
            'role="search"',
            "zola-docs-search.js",
            "version-switcher",
            'class="toc"',
            'class="breadcrumbs"',
            'aria-label="Page navigation"',
            'class="backlinks"',
            'class="edit-link"',
            'class="last-updated"',
            'rel="canonical"',
            'type="module"',
        )
        for needle in forbidden:
            if needle in page:
                raise RuntimeError(f"Disabled feature rendered: {needle}")


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
    run("python", "tests/navigation.test.py")
    run("python", "tests/converters.test.py")
    run("python", "tests/corpus.test.py")
    run("python", "tests/tombstones.test.py")
    check_demo(args.zola)
    check_consumer_override(args.zola)
    check_disabled_features(args.zola)
    run("node", "tests/search.test.js")
    print("theme demo, consumer override, responsive CSS, accessibility markup, and search: passed")


if __name__ == "__main__":
    main()
