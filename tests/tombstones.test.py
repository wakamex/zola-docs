#!/usr/bin/env python3

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from generate_version_tombstones import (  # noqa: E402
    STATE_MARKER,
    discover_routes,
    generate,
    load_versions,
    nearest_ancestor,
)
from benchmark_version_routes import analyze  # noqa: E402
from snapshot_routes import parse_mdbook_search_index, snapshot_sitemap  # noqa: E402


SHELL = """<!doctype html>
<html><head><title>Missing</title></head><body>
<!-- zola-docs-not-found-start -->
<h1>Page not found</h1>
<!-- zola-docs-not-found-end -->
</body></html>
"""


def write_site(root: Path, routes: list[str]) -> None:
    root.mkdir()
    (root / "404.html").write_text(SHELL)
    for route in routes:
        relative = route.removeprefix("/")
        if route == "/":
            destination = root / "index.html"
        elif route.endswith("/"):
            destination = root / relative / "index.html"
        else:
            destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(f"<html><body>{route}</body></html>")


with tempfile.TemporaryDirectory(prefix="zola-docs-tombstones-") as temporary:
    fixture = Path(temporary)
    write_site(fixture / "v1", ["/", "/guide/", "/legacy/"])
    write_site(fixture / "v2", ["/", "/guide/", "/guide/new/", "/only-v2.html"])
    write_site(fixture / "stable", ["/", "/guide/", "/guide/new/", "/only-v2.html"])
    config = fixture / "versions.toml"
    config.write_text(
        '''[[versions]]
id = "1.0"
label = "Version 1.0"
url = "https://docs.example.test/1.0/"
directory = "v1"
release_order = 1

[[versions]]
id = "2.0"
label = "Version 2.0"
url = "https://docs.example.test/2.0/"
directory = "v2"
release_order = 2

[[versions]]
id = "stable"
label = "Stable"
url = "/stable/"
directory = "stable"
'''
    )
    versions = load_versions(config)
    assert [version.id for version in versions] == ["1.0", "2.0", "stable"]
    output = fixture / "overlay"
    result = generate(versions, output)
    assert result["unique_routes"] == 5
    assert result["tombstones"] == 4
    assert result["by_version"] == {"1.0": 2, "2.0": 1, "stable": 1}

    introduced = (output / "1.0/guide/new/index.html").read_text()
    assert STATE_MARKER in introduced
    assert '<meta name="robots" content="noindex,follow">' in introduced
    assert 'data-route="/guide/new/"' in introduced
    assert "first appears in Version 2.0" in introduced
    assert 'href="https://docs.example.test/2.0/guide/new/"' in introduced
    assert 'href="/stable/guide/new/"' in introduced
    assert 'href="https://docs.example.test/1.0/guide/"' in introduced
    assert "Page not found" not in introduced

    removed = (output / "2.0/legacy/index.html").read_text()
    assert "Version 1.0" in removed
    assert "first appears in Version 1.0" in removed
    assert 'href="https://docs.example.test/2.0/"' in removed

    assert discover_routes(fixture / "v1") == {"/", "/guide/", "/legacy/"}
    assert nearest_ancestor("/guide/new/deep/", {"/", "/guide/"}) == "/guide/"
    assert nearest_ancestor("/missing.html", {"/"}) == "/"

    mdbook_source = "window.search = JSON.parse('{\"doc_urls\":[\"intro.html#one\",\"intro.html#two\",\"guide/start.html\"]}');"
    assert parse_mdbook_search_index(mdbook_source) == {
        "/",
        "/intro.html",
        "/guide/start.html",
    }
    legacy_mdbook_source = 'Object.assign(window.search, {"doc_urls":["old.html#part"]});'
    assert parse_mdbook_search_index(legacy_mdbook_source) == {"/", "/old.html"}

    sitemap = fixture / "sitemap.xml"
    sitemap.write_text(
        '''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://docs.example.test/1.0/</loc></url>
<url><loc>https://docs.example.test/1.0/guide/</loc></url>
<url><loc>https://docs.example.test/2.0/guide/</loc></url>
</urlset>'''
    )
    assert snapshot_sitemap(str(sitemap), "https://docs.example.test/1.0/") == {"/", "/guide/"}

    (fixture / "v1.routes").write_text("/\n/guide/\n/legacy/\n")
    (fixture / "v2.routes").write_text("/\n/guide/\n/guide/new/\n/only-v2.html\n")
    benchmark = fixture / "benchmark.toml"
    benchmark.write_text(
        '''[[sites]]
name = "Fixture docs"
shell_bytes = 5000

[[sites.versions]]
id = "1.0"
routes = "v1.routes"

[[sites.versions]]
id = "2.0"
routes = "v2.routes"
'''
    )
    measured = analyze(benchmark)[0]
    assert measured["unique_routes"] == 5
    assert measured["real_pages"] == 7
    assert measured["tombstones"] == 3
    assert measured["total_file_amplification"] == 1.4286
    assert measured["estimated_tombstone_bytes"] == 15_000

print("cross-version tombstone overlays and benchmarks: 26 checks passed")
