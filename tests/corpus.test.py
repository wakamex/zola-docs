#!/usr/bin/env python3

import json
import sys
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from convert_mdbook_site import (  # noqa: E402
    render_site,
    rewrite_target,
    route_for_source,
    summary_chapters,
)
from docs_corpus import load_manifest, normalized_routes  # noqa: E402


with tempfile.TemporaryDirectory(prefix="zola-docs-corpus-") as temporary:
    fixture = Path(temporary)
    source = fixture / "source"
    preprocessed = fixture / "preprocessed"
    output = fixture / "converted"
    (source / "src/img").mkdir(parents=True)
    preprocessed.mkdir()
    (source / "src/SUMMARY.md").write_text(
        "# Summary\n\n[Home](title.md)\n\n- [Guide](guide.md)\n  - [Detail](detail.md)\n"
    )
    (source / "src/img/diagram.svg").write_text("<svg></svg>\n")
    (preprocessed / "title.md").write_text(
        "# Home\n\n[Guide](guide.md)\n\n![Diagram](img/diagram.svg)\n"
    )
    (preprocessed / "guide.md").write_text("# Guide\n\n[Detail](detail.html#part)\n")
    (preprocessed / "detail.md").write_text("# Detail\n\nExpanded include.\n")
    document = {
        "book": {"title": "Fixture Book", "src": "src"},
        "output": {
            "html": {
                "git-repository-url": "https://example.test/book",
                "redirect": {"old-guide.html": "guide.html"},
            }
        },
    }
    result = render_site(source, preprocessed, output, ROOT, document)
    assert result == {"chapters": 3, "assets": 1}
    chapters = summary_chapters(source / "src/SUMMARY.md")
    assert [chapter.title for chapter in chapters] == ["Home", "Guide", "Detail"]
    assert chapters[2].branch_source == PurePosixPath("guide.md")
    assert route_for_source(PurePosixPath("title.md"), PurePosixPath("title.md")) == ""
    assert route_for_source(PurePosixPath("guide.md"), PurePosixPath("title.md")) == "guide/"
    navigation = json.loads((output / "data/navigation.json").read_text())
    assert navigation["groups"][0]["items"][0]["path"] == ""
    assert navigation["groups"][0]["items"][1]["children"][0]["path"] == "detail/"
    home = (output / "content/_index.md").read_text()
    assert "@/guide.md" in home
    assert "](/img/diagram.svg)" in home
    guide = (output / "content/guide.md").read_text()
    assert 'aliases = ["/old-guide.html"]' in guide
    assert "@/detail.md#part" in guide
    assert (output / "static/img/diagram.svg").is_file()
    assert rewrite_target(
        "missing.html", PurePosixPath("guide.md"), {PurePosixPath("guide.md")}, PurePosixPath("guide.md")
    ) == "missing.html"

    public = fixture / "public"
    (public / "guide").mkdir(parents=True)
    (public / "guide/index.html").write_text("guide")
    (public / "old.html").write_text("redirect")
    (public / "404.html").write_text("missing")
    assert normalized_routes(public) == {"/guide/", "/old/"}

    manifest = fixture / "site.toml"
    manifest.write_text(
        '''schema = 1
id = "fixture"
repository = "https://example.test/book.git"
revision = "abc"
adapter = "mdbook"
expected_native_only_routes = ["/print/"]

[[generators]]
id = "native"
cwd = "{source}"
command = ["native", "--output", "{output}"]
output = "{work}/native"
version_command = ["native", "--version"]
expected_version = "native 1.0"

[[generators]]
id = "zola-docs"
cwd = "{converted}"
command = ["{zola}", "build", "--output-dir", "{output}"]
output = "{work}/zola"
version_command = ["{zola}", "--version"]
expected_version = "zola 0.23.3"
'''
    )
    assert load_manifest(manifest)["expected_native_only_routes"] == ["/print/"]

print("full-site corpus conversion and contract: 18 checks passed")
