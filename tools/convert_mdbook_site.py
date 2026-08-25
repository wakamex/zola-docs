#!/usr/bin/env python3

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from convert_navigation import MDBOOK_LINK, MDBOOK_PART, convert_mdbook
from navigation import validate_navigation


MARKDOWN_LINK = re.compile(r"(?P<prefix>!?\[[^]]*]\()(?P<target>[^) \t]+)(?P<suffix>(?:[ \t]+[\"'][^\"']*[\"'])?\))")
HTML_LINK = re.compile(r'(?P<prefix>\b(?:href|src)=["\'])(?P<target>[^"\']+)(?P<suffix>["\'])')


class ConversionError(ValueError):
    pass


@dataclass(frozen=True)
class Chapter:
    title: str
    source: PurePosixPath
    group_index: int
    branch_source: PurePosixPath


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def summary_chapters(path: Path) -> list[Chapter]:
    chapters: list[Chapter] = []
    stack: list[tuple[int, PurePosixPath]] = []
    group_index = 0
    group_has_items = False
    for number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("<!--") or line.strip() == "---":
            continue
        part = MDBOOK_PART.match(line)
        if part:
            if part.group("title").lower() == "summary":
                continue
            if group_has_items:
                group_index += 1
            group_has_items = False
            stack.clear()
            continue
        link = MDBOOK_LINK.match(line)
        if not link:
            raise ConversionError(f"unsupported mdBook SUMMARY syntax on line {number}: {line}")
        group_has_items = True
        target = link.group("target").split("#", 1)[0].removeprefix("./")
        source = PurePosixPath(target)
        if source.suffix.lower() not in {".md", ".markdown"}:
            continue
        indent = len(link.group("indent").replace("\t", "    "))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        branch_source = stack[0][1] if stack else source
        chapters.append(Chapter(link.group("title"), source, group_index, branch_source))
        stack.append((indent, source))
    if not chapters:
        raise ConversionError("mdBook SUMMARY contains no Markdown chapters")
    return chapters


def route_for_source(source: PurePosixPath, first_source: PurePosixPath) -> str:
    if source == first_source:
        return ""
    without_suffix = source.with_suffix("")
    if without_suffix.name.lower() in {"readme", "index", "_index"}:
        parent = without_suffix.parent.as_posix().strip("./")
        return f"{parent}/" if parent else ""
    return f"{without_suffix.as_posix().strip('/')}/"


def preprocessed_source(source: PurePosixPath) -> PurePosixPath:
    if source.stem.lower() == "readme":
        return source.with_name("index.md")
    return source.with_suffix(".md")


def replace_navigation_path(nodes: list[dict[str, Any]], old: str, new: str) -> bool:
    for node in nodes:
        if node.get("path") == old:
            node["path"] = new
            return True
        children = node.get("children")
        if isinstance(children, list) and replace_navigation_path(children, old, new):
            return True
    return False


def rewrite_target(
    target: str,
    current_source: PurePosixPath,
    source_files: set[PurePosixPath],
    first_source: PurePosixPath,
) -> str:
    if not target or target.startswith(("#", "/", "mailto:", "http://", "https://")):
        return target
    path_text, marker, fragment = target.partition("#")
    if not path_text:
        return target
    relative = PurePosixPath(path_text)
    resolved = PurePosixPath(os.path.normpath((current_source.parent / relative).as_posix()))
    candidate = resolved.with_suffix(".md") if relative.suffix.lower() == ".html" else resolved
    if candidate in source_files:
        converted = PurePosixPath("_index.md") if candidate == first_source else candidate
        result = f"@/{converted.as_posix()}"
        return f"{result}#{fragment}" if marker else result
    if resolved.suffix.lower() not in {".md", ".markdown", ".html"}:
        result = "/" + resolved.as_posix().lstrip("/")
        return f"{result}#{fragment}" if marker else result
    return target


def rewrite_links(
    content: str,
    current_source: PurePosixPath,
    source_files: set[PurePosixPath],
    first_source: PurePosixPath,
) -> str:
    def markdown(match: re.Match[str]) -> str:
        target = rewrite_target(match.group("target"), current_source, source_files, first_source)
        return match.group("prefix") + target + match.group("suffix")

    def html_link(match: re.Match[str]) -> str:
        target = rewrite_target(match.group("target"), current_source, source_files, first_source)
        return match.group("prefix") + html.escape(target, quote=True) + match.group("suffix")

    return HTML_LINK.sub(html_link, MARKDOWN_LINK.sub(markdown, content))


def copy_assets(source_directory: Path, static_directory: Path) -> int:
    copied = 0
    for source in source_directory.rglob("*"):
        if not source.is_file() or source.suffix.lower() in {".md", ".markdown"}:
            continue
        relative = source.relative_to(source_directory)
        destination = static_directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1
    return copied


def render_site(
    source: Path,
    preprocessed: Path,
    output: Path,
    theme: Path,
    document: dict[str, Any],
) -> dict[str, int]:
    if output.exists():
        raise ConversionError(f"output already exists: {output}")
    book = document.get("book", {})
    source_name = book.get("src", "src")
    if not isinstance(source_name, str):
        raise ConversionError("book.src must be a string")
    source_directory = source / source_name
    summary = source_directory / "SUMMARY.md"
    chapters = summary_chapters(summary)
    first_source = chapters[0].source
    sources = {chapter.source for chapter in chapters}
    if len(sources) != len(chapters):
        raise ConversionError("mdBook SUMMARY contains duplicate chapter paths")

    title = book.get("title") or "Documentation"
    if not isinstance(title, str):
        raise ConversionError("book.title must be a string")
    navigation = convert_mdbook(summary, title, "book")
    first_route = route_for_source(first_source, first_source)
    original_first_route = route_for_source(first_source, PurePosixPath("__not_first__.md"))
    if not replace_navigation_path(navigation["groups"][0]["items"], original_first_route, first_route):
        raise ConversionError("first mdBook chapter is missing from converted navigation")
    validate_navigation(navigation)

    output.mkdir(parents=True)
    for directory in ("content", "data", "static", "templates", "themes"):
        (output / directory).mkdir()
    os.symlink(theme.resolve(), output / "themes/zola-docs", target_is_directory=True)

    repository = document.get("output", {}).get("html", {}).get("git-repository-url", "")
    edit_url = f"{repository.rstrip('/')}/edit" if isinstance(repository, str) and repository else ""
    (output / "config.toml").write_text(
        f'''title = {toml_string(title)}
base_url = "http://127.0.0.1:1111"
theme = "zola-docs"
compile_sass = false
build_search_index = true
generate_sitemap = true
generate_robots_txt = false

[markdown]
insert_anchor_links = "right"

[search]
index_format = "fuse_json"
include_title = true
include_content = true
include_path = true

[extra.zola_docs]
site_name = {toml_string(title)}
home_url = ""
navigation_path = "data/navigation.json"
search_enabled = true
versions_enabled = false
edit_url = {toml_string(edit_url)}
edit_branch = "main"
'''
    )
    (output / "data/navigation.json").write_text(
        json.dumps(navigation, indent=2, ensure_ascii=False) + "\n"
    )
    (output / "templates/page.html").write_text(
        '{% extends "zola-docs/templates/page.html" %}\n'
        "{% block page_header %}{% endblock page_header %}\n"
    )
    (output / "templates/section.html").write_text(
        '{% extends "zola-docs/templates/section.html" %}\n'
        "{% block section_header %}{% endblock section_header %}\n"
    )

    routes = {chapter.source: route_for_source(chapter.source, first_source) for chapter in chapters}
    group_ids = [group["id"] for group in navigation["groups"]]
    aliases: dict[PurePosixPath, list[str]] = {source: [] for source in sources}
    aliases[first_source].append("/" + first_source.with_suffix(".html").as_posix())
    redirects = document.get("output", {}).get("html", {}).get("redirect", {})
    if isinstance(redirects, dict):
        for alias, target in redirects.items():
            if not isinstance(alias, str) or not isinstance(target, str):
                raise ConversionError("output.html.redirect must map string routes to string routes")
            target_source = PurePosixPath(target.split("#", 1)[0]).with_suffix(".md")
            if target_source in sources:
                aliases[target_source].append("/" + alias.lstrip("/"))
    for index, chapter in enumerate(chapters):
        rendered_source = preprocessed / preprocessed_source(chapter.source)
        if not rendered_source.is_file():
            raise ConversionError(f"preprocessed chapter is missing: {rendered_source}")
        output_source = PurePosixPath("_index.md") if chapter.source == first_source else chapter.source
        destination = output / "content" / output_source
        destination.parent.mkdir(parents=True, exist_ok=True)
        previous = chapters[index - 1] if index else None
        following = chapters[index + 1] if index + 1 < len(chapters) else None
        frontmatter = [
            "+++",
            f"title = {toml_string(chapter.title)}",
        ]
        if aliases[chapter.source]:
            frontmatter.append(
                "aliases = [" + ", ".join(toml_string(alias) for alias in aliases[chapter.source]) + "]"
            )
        frontmatter.extend(
            [
                "[extra]",
                f"source_path = {toml_string(chapter.source.as_posix())}",
                f"navigation_group = {toml_string(group_ids[chapter.group_index])}",
                f"navigation_branch = {toml_string(routes[chapter.branch_source])}",
            ]
        )
        if previous is not None:
            frontmatter.append(
                f"previous = {{ title = {toml_string(previous.title)}, path = {toml_string(routes[previous.source])} }}"
            )
        if following is not None:
            frontmatter.append(
                f"next = {{ title = {toml_string(following.title)}, path = {toml_string(routes[following.source])} }}"
            )
        frontmatter.extend(["+++", ""])
        content = rewrite_links(rendered_source.read_text(), chapter.source, sources, first_source)
        destination.write_text("\n".join(frontmatter) + content)

    assets = copy_assets(source_directory, output / "static")
    return {"chapters": len(chapters), "assets": assets}


def convert(source: Path, output: Path, theme: Path, mdbook: str) -> dict[str, int]:
    if output.exists():
        raise ConversionError(f"output already exists: {output}")
    config_path = source / "book.toml"
    if not config_path.is_file():
        raise ConversionError(f"mdBook source lacks book.toml: {source}")
    document = tomllib.loads(config_path.read_text())
    with tempfile.TemporaryDirectory(prefix="zola-docs-mdbook-") as temporary:
        staging = Path(temporary)
        for child in source.iterdir():
            if child.name in {".git", "book", "book.toml"}:
                continue
            os.symlink(child.resolve(), staging / child.name, target_is_directory=child.is_dir())
        (staging / "book.toml").write_text(
            config_path.read_text().rstrip() + "\n\n[output.markdown]\n"
        )
        destination = staging / "build"
        subprocess.run([mdbook, "build", str(staging), "--dest-dir", str(destination)], check=True)
        result = render_site(source, destination / "markdown", output, theme, document)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a complete mdBook site to Zola Docs")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--theme", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mdbook", default="mdbook")
    args = parser.parse_args()
    try:
        result = convert(args.source.resolve(), args.output.resolve(), args.theme.resolve(), args.mdbook)
    except (OSError, subprocess.CalledProcessError, ConversionError, tomllib.TOMLDecodeError) as error:
        raise SystemExit(str(error)) from error
    print(f"converted {result['chapters']} chapters and {result['assets']} assets to {args.output}")


if __name__ == "__main__":
    main()
